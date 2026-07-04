"""Voca agent — Claude brain with Xero tools and confirm-before-write hooks."""

from __future__ import annotations

import os

import ai

from app.agent.prompts import SETUP_INTERVIEW_HINT, VOCA_SYSTEM
from app.agent.tools.xero import ALL_TOOLS
from app.config import get_settings
from app.session import get_session
from app.xero_client import is_connected

settings = get_settings()

if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

MODEL = ai.get_model(settings.ai_default_model)

voca_agent = ai.Agent(tools=ALL_TOOLS)


def system_prompt_for_session(session_id: str | None) -> str:
    parts = [VOCA_SYSTEM]

    if not session_id:
        return VOCA_SYSTEM

    session = get_session(session_id)
    connected = is_connected(session_id)
    parts.append(f"\nCurrent session_id for tool calls: {session_id}")
    parts.append(f"Xero connected: {'yes' if connected else 'no — general Q&A only; connect for live data and writes'}")

    if session.get("business_type"):
        parts.append(f"Known business type: {session['business_type']}")
    if session.get("org_type"):
        parts.append(f"Organisation type: {session['org_type']}")
    if session.get("vat_registered") is not None:
        scheme = session.get("vat_scheme", "none")
        parts.append(f"VAT: {'registered' if session['vat_registered'] else 'not registered'} ({scheme})")

    step = session.get("interview_step", 0)
    mode = session.get("mode", "setup")
    if mode == "setup" and 0 < step < 6:
        parts.append(SETUP_INTERVIEW_HINT.format(step=step))

    return "\n".join(parts)


def agent_for_session(session_id: str | None) -> ai.Agent:
    return voca_agent
