"""Wassist WhatsApp — BYOA webhooks + legacy custom-tool payloads."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date
from typing import Any

import httpx

from app.config import get_settings
from app.demo_state import set_receipt_mirror, update_demo_state
from app.receipt_ocr import extract_receipt
from app.session import get_session, save_session
from app.voice_agent import run_voca_voice_turn, try_voca_fast_reply
from app.voice_fast import is_fast_lookup, peek_voice_fast_cache, warm_voice_cache
from app.voice_receipt_fast import DEMO_RECEIPT_STUB, store_last_receipt
from app.xero_client import is_connected, latest_connected_connection_id, resolve_xero_connection

logger = logging.getLogger(__name__)

_TASK_KEYS = (
    "task",
    "instruction",
    "request",
    "query",
    "message",
    "user_message",
    "text",
    "user_request",
    "transcription",
    "transcript",
    "voice_transcript",
    "voice_note",
    "audio_transcript",
)
_META_KEYS = frozenset({"tool_call_id", "tool_name", "conversation_id", "parameters", "arguments"})


def session_id_for_connection(connection_id: str) -> str:
    return f"wa-{connection_id}"


def normalize_phone(phone: str) -> str:
    raw = (phone or "").strip()
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


_GREETING = re.compile(r"^(hi|hey|hello|hiya|yo|howdy)[\s!.?]*$", re.I)
_CASUAL = re.compile(r"^(what'?s up|whats up|sup|how are you|you good)[\s!.?]*$", re.I)
_GREETING_PREFIX = re.compile(r"^(hi|hey|hello|hiya|yo|howdy)[\s,!.?-]+", re.I)
_FOLLOW_UP = re.compile(
    r"\b(what'?s the update|any updates?|check again|still waiting|hello\?|you there|got an update)\b",
    re.I,
)
_in_flight: set[str] = set()
_recent_replies: dict[str, tuple[float, str]] = {}
_LOOP_PING_MARKERS = (
    "one sec - checking your xero",
    "one sec - working on that in xero",
    "one sec - reading your receipt",
    "still working on that in xero",
    "pulling your numbers from xero",
    "nearly there",
    "still pulling your numbers",
    "no customer message reply",
    "send a message or voice note",
    "sorry, i hit a snag",
    "sorry, i couldn't fetch",
)
_IMAGE_PLACEHOLDERS = frozenset({"%IMAGE_URL%", "%image_url%", "null", "none", "undefined"})


def _first_str(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = source.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def byoa_response(content: str) -> dict[str, str]:
    """Wassist BYOA / forward_message tool response — plain content is safest."""
    return {"content": sanitize_whatsapp_text(content)}


def byoa_no_reply() -> dict[str, str]:
    """Tell Wassist not to send another WhatsApp message (loop continuation ping)."""
    return {"content": "No CUSTOMER message reply"}


def sanitize_whatsapp_text(text: str) -> str:
    """Replace chars that garble on some WhatsApp clients."""
    return (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _normalize_image_url(image: Any) -> str | None:
    if image is None:
        return None
    if not isinstance(image, str):
        return None
    url = image.strip()
    if not url:
        return None
    if url.lower() in _IMAGE_PLACEHOLDERS:
        return None
    if url.startswith("%") and url.endswith("%"):
        return None
    if not url.startswith("http"):
        return None
    return url


def _greeting_reply(message: str) -> str | None:
    if _GREETING.match(message.strip()):
        return (
            "Hi - I'm Voca, your Xero bookkeeper. "
            "Ask me how much you're owed, send a receipt photo, or say "
            "'send invoice to Bayside Club for two hundred pounds plumbing'."
        )
    return None


def _casual_reply(message: str) -> str | None:
    if _CASUAL.match(message.strip()):
        return (
            "All good - I'm here. Ask what's owed, your latest invoice, "
            "or say send invoice to a customer."
        )
    return None


def _follow_up_text(message: str) -> str:
    """Re-run the most common demo query when user asks for an update."""
    if _FOLLOW_UP.search(message):
        return "how much am I owed this month"
    return message


def _normalize_user_message(message: str) -> str:
    text = message.strip()
    if _GREETING.match(text):
        return text
    stripped = _GREETING_PREFIX.sub("", text).strip()
    return stripped or text


def _in_flight_key(phone: str | None, connection_id: str) -> str:
    return phone or connection_id


def _dedupe_key(phone: str, message: str) -> str:
    return f"{phone}:{message.strip().lower()}"


def _get_recent_reply(phone: str, message: str) -> str | None:
    hit = _recent_replies.get(_dedupe_key(phone, message))
    if not hit:
        return None
    ts, reply = hit
    if time.time() - ts > 120:
        _recent_replies.pop(_dedupe_key(phone, message), None)
        return None
    return reply


def _store_recent_reply(phone: str, message: str, reply: str) -> None:
    _recent_replies[_dedupe_key(phone, message)] = (time.time(), reply)


def _is_wassist_loop_ping(message: str) -> bool:
    """Wassist echoes our tool output back as the next webhook message."""
    text = message.strip()
    if not text:
        return True
    lower = text.lower()
    return any(marker in lower for marker in _LOOP_PING_MARKERS)


# Wassist sends literal placeholders when no image is attached
    for key in keys:
        val = source.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


_REPLY_CALLBACK_TTL_SECS = 23 * 3600  # just under WhatsApp's 24h customer-service window


def store_recent_reply_callback(connection_id: str, phone: str, reply_callback: str) -> None:
    """Remember the latest reply_callback so we can push a proactive Xero-event
    notification later — only valid within WhatsApp's 24h customer-service window."""
    if not reply_callback:
        return
    session = get_session(connection_id)
    session["last_reply_callback"] = {"phone": phone, "callback": reply_callback, "ts": time.time()}
    save_session(connection_id, session)


def get_recent_reply_callback(connection_id: str) -> str | None:
    session = get_session(connection_id)
    data = session.get("last_reply_callback")
    if not isinstance(data, dict):
        return None
    if time.time() - float(data.get("ts", 0)) > _REPLY_CALLBACK_TTL_SECS:
        return None
    callback = data.get("callback")
    return callback if isinstance(callback, str) and callback else None


def link_whatsapp_phone(connection_id: str, phone: str) -> str:
    """Associate a WhatsApp number with a Xero connection (for BYOA routing)."""
    phone_e164 = normalize_phone(phone)
    if not phone_e164:
        raise ValueError("Invalid phone number")
    session = get_session(connection_id)
    session["whatsapp_phone"] = phone_e164
    save_session(connection_id, session)
    return phone_e164


def connection_for_whatsapp_phone(phone: str) -> str | None:
    phone_e164 = normalize_phone(phone)
    if not phone_e164:
        return None

    from app.db import db_enabled, get_conn

    if db_enabled():
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT session_id FROM voca_sessions
                WHERE state->>'whatsapp_phone' = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (phone_e164,),
            ).fetchone()
        if row:
            return row["session_id"]

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
        if data.get("whatsapp_phone") == phone_e164:
            return data.get("session_id")
    return None


def extract_wassist_fields(raw: dict[str, Any]) -> tuple[str, str | None]:
    """Parse legacy Wassist custom API tool payloads."""
    params = raw.get("parameters") or raw.get("arguments") or {}
    if not isinstance(params, dict):
        params = {}

    body_fields = {k: v for k, v in raw.items() if k not in _META_KEYS}
    sources = [params, body_fields, raw]

    task = ""
    for source in sources:
        task = _first_str(source, *_TASK_KEYS)
        if task:
            break

    if not task:
        skip_keys = _META_KEYS | {"tool_name", "tool_call_id", "connection_id", "phone_number", "reply_callback", "image"}
        strings = [
            v.strip()
            for source in sources
            if isinstance(source, dict)
            for k, v in source.items()
            if k not in skip_keys and isinstance(v, str) and v.strip()
        ]
        if strings:
            task = max(strings, key=len)

    connection_id = ""
    for source in sources:
        connection_id = _first_str(source, "connection_id")
        if connection_id:
            break

    return task, connection_id or None


def parse_byoa_payload(raw: dict[str, Any]) -> tuple[str, str | None, str, str]:
    """BYOA fields: message, image URL, phone, reply_callback."""
    message = _first_str(raw, "message", "text") or ""
    image_url = _normalize_image_url(raw.get("image"))
    phone = normalize_phone(_first_str(raw, "phone_number", "phone"))
    reply_callback = _first_str(raw, "reply_callback")
    return message, image_url, phone, reply_callback


def demo_connection_id() -> str | None:
    """Single Xero org for hackathon demo (Demo Company UK)."""
    settings = get_settings()
    cid = (settings.wassist_default_connection_id or "").strip()
    if cid:
        return cid
    if settings.environment == "development":
        return latest_connected_connection_id()
    return None


def resolve_connection_id(
    *,
    explicit: str | None = None,
    phone: str | None = None,
) -> tuple[str | None, str | None]:
    """Return (connection_id, user-facing error). All WhatsApp → one demo org."""
    settings = get_settings()
    connection_id = demo_connection_id() or explicit

    if not connection_id:
        return None, (
            "Xero isn't set up yet. Connect Demo Company in the Voca app and set "
            "WASSIST_DEFAULT_CONNECTION_ID in .env."
        )

    resolve_xero_connection(connection_id, [])
    if not is_connected(connection_id):
        return None, "Xero isn't connected. Open the Voca app and connect Demo Company (UK)."

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        asyncio.create_task(warm_voice_cache(connection_id))
    return connection_id, None


def resolve_connection(raw: dict[str, Any]) -> tuple[str | None, dict[str, str] | None]:
    """Legacy custom-tool resolver."""
    _, explicit = extract_wassist_fields(raw)
    phone = normalize_phone(_first_str(raw, "phone_number", "phone"))
    connection_id, err = resolve_connection_id(explicit=explicit, phone=phone or None)
    if err:
        return None, {"result": err}
    return connection_id, None


async def store_receipt_stub(
    connection_id: str, image_url: str | bytes = "", caption: str = ""
) -> str:
    """Extract vendor/amount/category from a receipt photo via vision OCR.

    Falls back to a canned Shell receipt if there's no image URL to read (legacy
    callers) or the OCR call itself fails, so the flow never dead-ends.
    """
    note = ""
    if image_url:
        try:
            extraction = await extract_receipt(image_url, caption)
            vendor = extraction.vendor
            amount_gbp = extraction.amount_gbp
            category = extraction.category
            receipt_date = extraction.date or date.today().isoformat()
            note = extraction.note
        except Exception:
            logger.exception("Receipt OCR failed, falling back to demo stub")
            vendor, amount_gbp, category = (
                DEMO_RECEIPT_STUB["vendor"],
                DEMO_RECEIPT_STUB["amount_gbp"],
                DEMO_RECEIPT_STUB["category"],
            )
            receipt_date = date.today().isoformat()
    else:
        vendor, amount_gbp, category = (
            DEMO_RECEIPT_STUB["vendor"],
            DEMO_RECEIPT_STUB["amount_gbp"],
            DEMO_RECEIPT_STUB["category"],
        )
        receipt_date = date.today().isoformat()

    chat_session_id = session_id_for_connection(connection_id)
    store_last_receipt(chat_session_id, vendor=vendor, amount_gbp=amount_gbp, category=category)
    set_receipt_mirror(
        connection_id,
        vendor=vendor,
        amount_gbp=amount_gbp,
        category=category,
        in_xero=False,
    )
    update_demo_state(connection_id, last_whatsapp_at=receipt_date)
    reply = f"Got it — {vendor}, £{amount_gbp:.2f}, {category}. Say add that to Xero when you're ready."
    if note:
        reply += f" ({note})"
    return reply


async def _answer_sync(
    *,
    chat_session_id: str,
    connection_id: str,
    message: str,
    phone_key: str,
) -> str:
    """Answer in the webhook response — Wassist callbacks are unreliable."""
    flight_key = _in_flight_key(
        None if phone_key == "unknown" else phone_key,
        connection_id,
    )
    if flight_key in _in_flight:
        recent = _get_recent_reply(phone_key, message)
        if recent:
            return recent
        raise RuntimeError("Still working on your last question - try again in a moment.")

    _in_flight.add(flight_key)
    try:
        if is_fast_lookup(message):
            cached = peek_voice_fast_cache(connection_id, message)
            if cached:
                _store_recent_reply(phone_key, message, cached)
                return cached
            reply = await try_voca_fast_reply(
                chat_session_id=chat_session_id,
                connection_id=connection_id,
                user_text=message,
            )
        else:
            reply = await try_voca_fast_reply(
                chat_session_id=chat_session_id,
                connection_id=connection_id,
                user_text=message,
            )
            if not reply:
                reply = await _run_turn(connection_id, message)
        if not reply:
            reply = "Sorry, I couldn't work that out. Try asking what's owed or your latest invoice."
        _store_recent_reply(phone_key, message, reply)
        return reply
    finally:
        _in_flight.discard(flight_key)


async def _run_turn(connection_id: str, user_text: str) -> str:
    return await run_voca_voice_turn(
        chat_session_id=session_id_for_connection(connection_id),
        connection_id=connection_id,
        user_text=user_text,
    )


async def _byoa_turn_async(
    connection_id: str,
    user_text: str,
    reply_callback: str,
    *,
    phone: str = "",
) -> None:
    """Slow path only (invoices etc.) — fetch then POST via reply_callback."""
    key = _in_flight_key(phone or None, connection_id)
    done = asyncio.Event()

    async def interim_updates() -> None:
        await asyncio.sleep(4)
        if done.is_set():
            return
        await send_byoa_reply(
            reply_callback,
            "Still working on that in Xero - might take a minute or two.",
        )

    interim_task = asyncio.create_task(interim_updates())
    try:
        reply = await _run_turn(connection_id, user_text)
    except Exception as exc:
        logger.exception("BYOA async turn failed")
        reply = f"Sorry, I hit a snag: {exc}"
    finally:
        done.set()
        interim_task.cancel()
        try:
            await interim_task
        except asyncio.CancelledError:
            pass
        _in_flight.discard(key)

    if phone:
        _store_recent_reply(phone, user_text, reply)
        _maybe_send_document_bubble(phone, reply)
    logger.info("BYOA final callback len=%d url=%s", len(reply), reply_callback[:70])
    await send_byoa_reply(reply_callback, reply)


async def _byoa_receipt_turn_async(
    connection_id: str,
    image_url: str,
    caption: str,
    reply_callback: str,
    *,
    phone: str = "",
) -> None:
    """OCR + optional Xero write (e.g. "add to Xero") — can take 10s+, so this
    runs after the immediate ack and delivers the real result via reply_callback."""
    key = _in_flight_key(phone or None, connection_id)
    chat_session_id = session_id_for_connection(connection_id)
    try:
        receipt_reply = await store_receipt_stub(connection_id, image_url, caption)
        reply = receipt_reply
        if caption.strip():
            fast_reply = await try_voca_fast_reply(
                chat_session_id=chat_session_id,
                connection_id=connection_id,
                user_text=caption,
            )
            if fast_reply:
                reply = f"{receipt_reply}\n\n{fast_reply}"
    except Exception as exc:
        logger.exception("BYOA async receipt turn failed")
        reply = f"Sorry, I hit a snag reading that receipt: {exc}"
    finally:
        _in_flight.discard(key)

    if phone:
        _store_recent_reply(phone, caption, reply)
        _maybe_send_document_bubble(phone, reply)
    logger.info("BYOA final receipt callback len=%d url=%s", len(reply), reply_callback[:70])
    await send_byoa_reply(reply_callback, reply)


async def send_byoa_reply(reply_callback: str, content: str) -> None:
    # reply_callback is a pre-authenticated, single-use URL (session + tool-call-id
    # baked into the path) — per Wassist's docs example it takes no auth header.
    # Sending our admin X-API-Key here is unnecessary and unverified against their
    # callback endpoint, so don't attach it.
    headers = {"Content-Type": "application/json"}
    body = {"type": "message", "content": sanitize_whatsapp_text(content)}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                reply_callback,
                json=body,
                headers=headers,
                timeout=30.0,
            )
            if response.status_code >= 400:
                logger.error(
                    "BYOA callback failed status=%s body=%s url=%s",
                    response.status_code,
                    response.text[:300],
                    reply_callback[:80],
                )
                response.raise_for_status()
            logger.info(
                "BYOA callback OK status=%s len=%d resp_body=%s",
                response.status_code,
                len(content),
                response.text[:300],
            )
    except Exception:
        logger.exception("failed to POST BYOA reply_callback url=%s", reply_callback[:80])


# .pdf attachments are silently dropped by WhatsApp on Wassist's shared sandbox
# number (confirmed via live testing — Wassist's API reports full success,
# WhatsApp just never delivers the document). Images deliver fine on the same
# number, so the chart PNG — not the PDF — is the one we actually push as a
# native attachment.
_OWN_CHART_URL = re.compile(r"https?://\S+/files/mtd-summary\.png\?\S+")


def _maybe_send_document_bubble(phone: str, reply: str) -> None:
    """Fire-and-forget: if a reply contains our own MTD chart PNG link, also
    try delivering it as a native WhatsApp image bubble (better UX than a bare
    link), without blocking or affecting the guaranteed plain-text reply."""
    if not phone:
        return
    match = _OWN_CHART_URL.search(reply)
    if not match:
        return
    asyncio.create_task(
        send_document_via_wassist(phone, match.group(0), "Your MTD tax pack")
    )


async def send_document_via_wassist(phone: str, file_url: str, caption: str = "") -> bool:
    """Send a file as a native WhatsApp document bubble, via Wassist's REST API
    (not the BYOA reply_callback — a separate, fully-documented mechanism):
    look up the conversation for this phone, then POST a "unified" message with
    a media URL. Verified working end-to-end (Wassist fetches the file, uploads
    it to WhatsApp's media API, confirms mimeType) — but that round trip takes
    30-45s, hence the generous timeout below.
    """
    settings = get_settings()
    if not settings.wassist_api_key:
        return False
    headers = {"X-API-Key": settings.wassist_api_key, "Content-Type": "application/json"}
    base = settings.wassist_api_base.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            lookup = await client.get(
                f"{base}/api/v1/conversations/",
                headers=headers,
                # Wassist stores contact numbers without the leading "+"
                params={"contact": phone.lstrip("+")},
            )
            lookup.raise_for_status()
            results = lookup.json().get("results") or []
            if not results:
                logger.info("send_document_via_wassist: no conversation found for phone=%s", phone)
                return False
            conversation_id = results[0]["id"]

            send = await client.post(
                f"{base}/api/v1/conversations/{conversation_id}/messages/",
                headers=headers,
                json={
                    "type": "unified",
                    "unified": {"text": caption[:1024], "media": {"url": file_url}},
                },
            )
            if send.status_code >= 400:
                logger.error(
                    "send_document_via_wassist failed status=%s body=%s",
                    send.status_code,
                    send.text[:300],
                )
                return False
            logger.info("send_document_via_wassist OK conversation=%s", conversation_id)
            return True
    except Exception:
        logger.exception("send_document_via_wassist errored for phone=%s", phone)
        return False


async def handle_byoa_webhook(raw: dict[str, Any]) -> dict[str, str]:
    """
    Wassist Bring Your Own Agent webhook.
    Docs: https://docs.wassist.app/concepts/bring-your-own-agent

    Wassist times out around 5-7s. When reply_callback is present, ack immediately
    and send interim + final messages via callback (multi-message WhatsApp flow).
    """
    message, image_url, phone, reply_callback = parse_byoa_payload(raw)
    explicit = _first_str(raw, "connection_id")

    if _is_wassist_loop_ping(message):
        logger.info("BYOA loop ping ignored phone=%s message=%r", phone or "?", message[:60])
        return byoa_no_reply()

    logger.info(
        "BYOA inbound phone=%s message=%r image=%s callback=%s",
        phone or "?",
        message[:80],
        bool(image_url),
        bool(reply_callback),
    )
    connection_id, err = resolve_connection_id(explicit=explicit or None, phone=phone or None)
    if err:
        return byoa_response(err)

    if reply_callback:
        store_recent_reply_callback(connection_id, phone, reply_callback)

    flight_key = _in_flight_key(phone or None, connection_id)
    if _FOLLOW_UP.search(message.strip()) and flight_key in _in_flight:
        return byoa_response("Still pulling your numbers from Xero - I will message you in a moment.")

    message = _normalize_user_message(_follow_up_text(message))

    greeting = _greeting_reply(message)
    if greeting and not image_url:
        asyncio.create_task(warm_voice_cache(connection_id))
        return byoa_response(greeting)

    casual = _casual_reply(message)
    if casual and not image_url:
        return byoa_response(casual)

    chat_session_id = session_id_for_connection(connection_id)

    if image_url:
        # OCR + a possible Xero write (e.g. "add to Xero") can take 10s+ combined —
        # too slow for Wassist's webhook timeout. Ack now and deliver via callback.
        if reply_callback:
            _in_flight.add(flight_key)
            asyncio.create_task(
                _byoa_receipt_turn_async(
                    connection_id, image_url, message, reply_callback, phone=phone or ""
                )
            )
            return byoa_response("One sec - reading your receipt, I will message you shortly.")
        receipt_reply = await store_receipt_stub(connection_id, image_url, message)
        # Only append a second message for a recognized command alongside the photo
        # (e.g. "add that to Xero") — the general agent has no view of the image, so
        # routing arbitrary captions to it just produces a confusing "I can't see
        # images" reply that contradicts the OCR result above.
        if message.strip():
            try:
                fast_reply = await try_voca_fast_reply(
                    chat_session_id=chat_session_id,
                    connection_id=connection_id,
                    user_text=message,
                )
                if fast_reply:
                    return byoa_response(f"{receipt_reply}\n\n{fast_reply}")
            except Exception as exc:
                logger.exception("BYOA fast-path after receipt failed")
                return byoa_response(f"{receipt_reply}\n\n(Sorry, I couldn't finish: {exc})")
        return byoa_response(receipt_reply)

    if not message.strip():
        if reply_callback:
            return byoa_no_reply()
        return byoa_response("Send a message or voice note - what should I do in Xero?")

    phone_key = phone or "unknown"
    recent = _get_recent_reply(phone_key, message)
    if recent:
        logger.info("BYOA dedupe hit phone=%s", phone or "?")
        return byoa_response(recent)

    if flight_key in _in_flight:
        return byoa_no_reply()

    # Fast lookups (or no callback to deliver a follow-up on) answer inline —
    # they're quick enough to fit inside Wassist's webhook timeout.
    if is_fast_lookup(message) or not reply_callback:
        try:
            reply = await _answer_sync(
                chat_session_id=chat_session_id,
                connection_id=connection_id,
                message=message,
                phone_key=phone_key,
            )
            logger.info("BYOA sync reply phone=%s len=%d", phone or "?", len(reply))
            _maybe_send_document_bubble(phone, reply)
            return byoa_response(reply)
        except Exception as exc:
            logger.exception("BYOA sync turn failed")
            return byoa_response(f"Something went wrong: {exc}")

    # Slow path (full Xero agent — invoice writes, open-ended questions): the
    # webhook response would otherwise race Wassist's short timeout and the
    # real answer never reaches the user. Ack now and deliver the answer (plus
    # an interim ping) via reply_callback instead. The ack/ping text is in
    # _LOOP_PING_MARKERS so Wassist echoing it back as a new inbound message
    # is recognized and ignored rather than looping.
    _in_flight.add(flight_key)
    _schedule_byoa_turn(connection_id, message, reply_callback, phone=phone or "")
    return byoa_response("One sec - checking your Xero, I will message you shortly.")


def _schedule_byoa_turn(
    connection_id: str,
    user_text: str,
    reply_callback: str,
    *,
    phone: str = "",
) -> None:
    # FastAPI's BackgroundTasks runs async tasks in-line before the response is
    # flushed to the client (it awaits them as part of the same ASGI response
    # cycle), which defeats the "ack now, work in background" design. A bare
    # asyncio.create_task actually detaches the turn from the response cycle.
    asyncio.create_task(
        _byoa_turn_async(connection_id, user_text, reply_callback, phone=phone)
    )


async def handle_wassist_message(raw: dict[str, Any]) -> dict[str, str]:
    """Legacy Wassist custom API tool — returns { result }."""
    task, _ = extract_wassist_fields(raw)
    if not task:
        return {"result": "I didn't catch that. Send a message or voice note — what should I do in Xero?"}

    connection_id, err = resolve_connection(raw)
    if err:
        return err

    try:
        reply = await _run_turn(connection_id, task)
    except Exception as exc:
        logger.exception("wassist webhook failed")
        return {"result": f"Something went wrong: {exc}"}
    return {"result": reply}
