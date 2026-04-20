from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .run_store import RunStore


class EventLogger:
    def __init__(self, run_store: RunStore):
        self.run_store = run_store

    def log(self, run_id: str, event: dict[str, Any]) -> Path:
        run_dir = self.run_store.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "events.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            **event,
        }
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return path
