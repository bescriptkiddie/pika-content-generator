from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver


def build_checkpointer(storage_path: str | None = None):
    """Return a checkpointer implementation.

    First version keeps persistence surface stable while using MemorySaver.
    storage_path is reserved for future file/postgres-backed checkpointers.
    """
    _ = Path(storage_path).resolve() if storage_path else None
    return MemorySaver()
