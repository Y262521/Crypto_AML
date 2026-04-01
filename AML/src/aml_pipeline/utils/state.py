"""Small JSON state helpers for incremental ETL."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_STATE = {"last_extracted_at": None}


def load_state(state_path: Path) -> dict:
    """Load pipeline state from disk or return defaults if missing."""
    if not state_path.exists():
        return DEFAULT_STATE.copy()
    with state_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state_path: Path, state: dict) -> None:
    """Persist pipeline state to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def get_last_extracted_at(state: dict) -> Optional[datetime]:
    """Parse and return the last extraction timestamp from state."""
    value = state.get("last_extracted_at")
    if not value:
        return None
    return datetime.fromisoformat(value)


def set_last_extracted_at(state: dict, dt: datetime) -> dict:
    """Update state with the latest extraction timestamp."""
    state["last_extracted_at"] = dt.astimezone(timezone.utc).isoformat()
    return state
