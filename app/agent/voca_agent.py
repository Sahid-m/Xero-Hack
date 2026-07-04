"""Voca agent — Claude brain with Xero tools and confirm-before-write hooks."""

from __future__ import annotations

import os

import ai

from app.agent.prompts import OPERATIONS_SYSTEM, SETUP_SYSTEM
from app.agent.tools.xero import ALL_TOOLS, OPERATIONS_TOOLS, SETUP_TOOLS
from app.config import get_settings
from app.session import session_mode

settings = get_settings()

if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

MODEL = ai.get_model(settings.ai_default_model)

setup_agent = ai.Agent(tools=SETUP_TOOLS)
operations_agent = ai.Agent(tools=OPERATIONS_TOOLS)
voca_agent = ai.Agent(tools=ALL_TOOLS)


def system_prompt_for_session(session_id: str | None) -> str:
    mode = session_mode(session_id)
    base = SETUP_SYSTEM if mode == "setup" else OPERATIONS_SYSTEM
    if session_id:
        return f"{base}\n\nCurrent session_id for tool calls: {session_id}"
    return base


def agent_for_session(session_id: str | None) -> ai.Agent:
    return setup_agent if session_mode(session_id) == "setup" else operations_agent
