from __future__ import annotations

from pathlib import Path

RUNS_ROOT = Path(__file__).resolve().parents[2] / "data" / "runs"
RUNS_ROOT.mkdir(parents=True, exist_ok=True)
