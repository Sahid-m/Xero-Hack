"""Session state for setup interview progress and learned preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from app.db import db_enabled, load_session_state as db_load, save_session_state as db_save

SessionMode = Literal["setup", "operations"]

DATA_DIR = Path("data/sessions")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(session_id: str) -> Path:
    safe = session_id.replace("/", "__").replace(":", "_")
    return DATA_DIR / f"{safe}.json"


def _file_load(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.exists():
        return {
            "session_id": session_id,
            "mode": "setup",
            "interview_step": 0,
            "business_type": None,
            "vat_registered": None,
            "contacts": [],
            "rates": {},
        }
    return json.loads(path.read_text())


def _file_save(session_id: str, data: dict[str, Any]) -> None:
    _path(session_id).write_text(json.dumps(data, indent=2))


def get_session(session_id: str) -> dict[str, Any]:
    if db_enabled():
        return db_load(session_id)
    return _file_load(session_id)


def save_session(session_id: str, data: dict[str, Any]) -> None:
    if db_enabled():
        db_save(session_id, data)
    else:
        _file_save(session_id, data)


def session_mode(session_id: str | None) -> SessionMode:
    if not session_id:
        return "setup"
    return get_session(session_id).get("mode", "setup")
