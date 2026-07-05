"""Real receipt OCR — extract vendor/amount/category from a photo via vision LLM."""

from __future__ import annotations

import logging

import ai
import httpx
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
OCR_MODEL = ai.get_model(settings.voice_ai_model)

_SYSTEM = """\
You are a receipt scanner for a UK bookkeeping app. Read the receipt image and extract:

- vendor: the merchant/business name as printed on the receipt
- amount_gbp: the total amount paid, in GBP. If the receipt shows a different currency, \
convert using an approximate rate and note the original amount/currency in `note`.
- category: a short UK expense category (e.g. "Motor expenses", "Meals & entertainment", \
"Office supplies", "Travel", "Utilities", "Professional fees")
- date: the receipt date in YYYY-MM-DD format if visible, otherwise omit
- note: any caveat worth flagging (currency conversion, illegible amount, not a receipt, etc.) \
or empty string if none

If the image is not a legible receipt, do your best guess and set `note` to explain why the \
extraction may be unreliable. Always return your best-effort numbers — never refuse."""


class ReceiptExtraction(BaseModel):
    vendor: str = Field(description="Merchant name")
    amount_gbp: float = Field(description="Total amount in GBP")
    category: str = Field(description="UK expense category")
    date: str | None = Field(default=None, description="Receipt date, YYYY-MM-DD")
    note: str = Field(default="", description="Caveats, e.g. currency conversion")


async def _load_image_bytes(image_url: str | bytes) -> bytes:
    """Download the image ourselves rather than passing the URL through.

    Wassist-hosted media URLs have no file extension (e.g.
    ".../images/166722129771"), so URL-based media-type sniffing
    (mimetypes.guess_type) fails. Fetching the bytes lets us detect the
    real type from magic bytes instead, which always works.
    """
    if isinstance(image_url, bytes):
        return image_url
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


async def extract_receipt(image_url: str | bytes, caption: str = "") -> ReceiptExtraction:
    """Run the receipt photo through a vision model and return structured fields."""
    image_bytes = await _load_image_bytes(image_url)
    parts = [ai.file_part(image_bytes)]
    if caption.strip():
        parts.append(ai.text_part(caption.strip()))

    messages = [ai.system_message(_SYSTEM), ai.user_message(*parts)]
    agent = ai.Agent()
    async with agent.run(OCR_MODEL, messages, output_type=ReceiptExtraction) as stream:
        async for _event in stream:
            pass
    return stream.output
