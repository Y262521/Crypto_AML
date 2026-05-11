from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class WatchlistManager:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "watchlist.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_entries(self) -> list[dict[str, Any]]:
        return self._read()

    def add_entry(
        self,
        *,
        address: str,
        chain: str,
        category: str,
        source: str,
        confidence: float,
        reviewer_notes: str = "",
        label: str = "",
    ) -> dict[str, Any]:
        entries = self._read()
        entry = {
            "id": str(uuid4()),
            "address": address,
            "chain": chain,
            "category": category,
            "source": source,
            "confidence": confidence,
            "reviewer_notes": reviewer_notes,
            "label": label,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        entries.append(entry)
        self._write(entries)
        return entry

    def update_entry(self, entry_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        entries = self._read()
        for entry in entries:
            if entry["id"] != entry_id:
                continue
            entry.update(updates)
            entry["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
            self._write(entries)
            return entry
        return None

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
