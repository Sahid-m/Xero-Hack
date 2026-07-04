"""Per-request Voca session binding for tool calls."""

from __future__ import annotations

from contextvars import ContextVar, Token

_voca_session_id: ContextVar[str | None] = ContextVar("voca_session_id", default=None)


def bind_voca_session(session_id: str | None) -> Token:
    return _voca_session_id.set(session_id)


def reset_voca_session(token: Token) -> None:
    _voca_session_id.reset(token)


def voca_session_id() -> str:
    session_id = _voca_session_id.get()
    if not session_id:
        raise RuntimeError("No active Voca session — refresh the page and try again.")
    return session_id
