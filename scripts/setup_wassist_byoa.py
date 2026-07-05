#!/usr/bin/env python3
"""Register Voca as a Wassist BYOA agent — https://docs.wassist.app/concepts/bring-your-own-agent"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def main() -> int:
    settings = get_settings()
    if not settings.wassist_api_key:
        print("Set WASSIST_API_KEY in .env (Wassist → Settings → API Keys)")
        return 1
    if not settings.public_base_url:
        print("Set PUBLIC_BASE_URL in .env (your ngrok or deploy URL)")
        return 1

    webhook_url = f"{settings.public_base_url.rstrip('/')}/whatsapp/byoa"
    api_url = f"{settings.wassist_api_base.rstrip('/')}/api/v1/agents/byoa/"

    print("Voca × Wassist BYOA")
    print(f"  API:     {api_url}")
    print(f"  Webhook: {webhook_url}")
    print()

    response = httpx.post(
        api_url,
        headers={
            "X-API-Key": settings.wassist_api_key,
            "Content-Type": "application/json",
        },
        json={"webhookUrl": webhook_url},
        timeout=30.0,
    )

    if response.status_code not in (200, 201):
        print(f"Failed ({response.status_code}): {response.text[:500]}")
        print("\nIf 404, try WASSIST_API_BASE=https://wassist.app")
        return 1

    agent = response.json()
    print("Agent created:")
    print(json.dumps(agent, indent=2)[:2000])

    connect = agent.get("connectUrl")
    if connect:
        print(f"\nTest in Wassist sandbox: {connect}")
        print("Open that URL, send a WhatsApp message, and Voca should reply.")

    print("\nOptional .env for single-user demo (skip phone linking):")
    print(f"  WASSIST_DEFAULT_CONNECTION_ID=<your connection_id after Connect Xero>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
