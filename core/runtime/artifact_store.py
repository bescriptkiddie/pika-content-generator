from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .run_store import RunStore


class ArtifactStore:
    def __init__(self, run_store: RunStore):
        self.run_store = run_store

    def write_stage_artifact(self, run_id: str, stage: str, payload: dict[str, Any]) -> Path:
        run_dir = self.run_store.run_dir(run_id)
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / f"{stage}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
