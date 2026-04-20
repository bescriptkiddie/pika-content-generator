from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import RUNS_ROOT


class RunStore:
    def __init__(self, root: Path | None = None):
        self.root = root or RUNS_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def init_run(self, run_id: str, record: dict[str, Any]) -> Path:
        run_dir = self.root / run_id
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        payload = {
            **record,
            "run_id": run_id,
            "status": record.get("status", "running"),
            "started_at": record.get("started_at", datetime.now().isoformat()),
        }
        self._write_json(run_dir / "run.json", payload)
        return run_dir

    def update_run(self, run_id: str, patch: dict[str, Any]) -> None:
        run_dir = self.root / run_id
        path = run_dir / "run.json"
        current = self.read_run(run_id)
        current.update(patch)
        self._write_json(path, current)

    def read_run(self, run_id: str) -> dict[str, Any]:
        path = self.root / run_id / "run.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
