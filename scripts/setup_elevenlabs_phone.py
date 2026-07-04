#!/usr/bin/env python3
"""Print ElevenLabs + Twilio setup steps for Voca phone agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings

CONFIG_PATH = Path(__file__).parent / "elevenlabs_agent_config.json"


def main() -> None:
    settings = get_settings()
    public_url = settings.public_base_url or os.environ.get("PUBLIC_BASE_URL", "https://YOUR-NGROK-URL")

    print("=" * 60)
    print("Voca Phone Agent — ElevenLabs + Twilio Setup")
    print("=" * 60)
    print()
    print("1. Twilio: buy or use a phone number")
    print("2. ElevenLabs → Agents → Create agent (or import config below)")
    print("3. ElevenLabs → Phone Numbers → Import Twilio number")
    print("4. Assign your Voca agent to that number")
    print()
    print("Webhooks (set PUBLIC_BASE_URL in .env):")
    print(f"  Conversation init:  {public_url}/voice/init")
    print(f"  Server tool:        {public_url}/voice/tools/delegate")
    print()
    print("Env vars:")
    print(f"  ELEVENLABS_API_KEY     {'✓' if settings.elevenlabs_api_key else '✗'}")
    print(f"  ELEVENLABS_AGENT_ID    {settings.elevenlabs_agent_id or '(set after creating agent)'}")
    print(f"  VOCA_PHONE_NUMBER      {settings.voca_phone_number or '(your Twilio number, e.g. +447...)'}")
    print(f"  PUBLIC_BASE_URL        {public_url}")
    print()
    print("User flow:")
    print("  1. Connect Xero in the web app")
    print("  2. Link mobile number (Call Voca card)")
    print("  3. Call the number and delegate tasks by voice")
    print()

    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        tool = config["tools"][0]
        tool["api_schema"]["url"] = f"{public_url.rstrip('/')}/voice/tools/delegate"
        print("Agent tool config (paste into ElevenLabs webhook tool):")
        print(json.dumps(tool, indent=2))
        print()

    if settings.elevenlabs_api_key and settings.elevenlabs_agent_id:
        print("Optional: create outbound test call via ElevenLabs dashboard")
        print(f"  Agent ID: {settings.elevenlabs_agent_id}")


if __name__ == "__main__":
    main()
