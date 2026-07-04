"""Per-request chat + Xero connection binding for tool calls."""

from __future__ import annotations

from contextvars import ContextVar, Token

_chat_session_id: ContextVar[str | None] = ContextVar("chat_session_id", default=None)
_xero_connection_id: ContextVar[str | None] = ContextVar("xero_connection_id", default=None)


def bind_request_context(
    chat_session_id: str | None,
    xero_connection_id: str | None,
) -> tuple[Token, Token]:
    chat_token = _chat_session_id.set(chat_session_id)
    xero_token = _xero_connection_id.set(xero_connection_id or chat_session_id)
    return chat_token, xero_token


def reset_request_context(chat_token: Token, xero_token: Token) -> None:
    _chat_session_id.reset(chat_token)
    _xero_connection_id.reset(xero_token)


def chat_session_id() -> str:
    session_id = _chat_session_id.get()
    if not session_id:
        raise RuntimeError("No active chat session — refresh the page and try again.")
    return session_id


def xero_connection_id() -> str:
    connection_id = _xero_connection_id.get() or _chat_session_id.get()
    if not connection_id:
        raise RuntimeError("No active Xero connection — refresh the page and try again.")
    return connection_id


# Back-compat alias used by setup tools
def voca_session_id() -> str:
    return chat_session_id()
