from __future__ import annotations

from collections.abc import Callable
from typing import Any

StageHandler = Callable[..., Any]

_REGISTRY: dict[str, dict[str, StageHandler]] = {
    "acquire": {},
    "analyze": {},
    "generate": {},
    "execute": {},
    "feedback": {},
}


def register(stage: str, scene: str, handler: StageHandler) -> None:
    _REGISTRY.setdefault(stage, {})[scene] = handler


def get_handler(stage: str, scene: str, default: StageHandler | None = None) -> StageHandler | None:
    return _REGISTRY.get(stage, {}).get(scene, default)


def list_bindings() -> dict[str, list[str]]:
    return {stage: sorted(bindings.keys()) for stage, bindings in _REGISTRY.items()}
