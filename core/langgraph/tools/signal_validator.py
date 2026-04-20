from __future__ import annotations

from typing import Any


VERIFICATION_DETAIL_KEYS = (
    "verification_required",
    "verify_type",
    "verify_uuid",
)


def is_usable_signal(items: list[dict], *, minimum_count: int = 1) -> bool:
    valid_items = [item for item in items if _is_usable_item(item)]
    return len(valid_items) >= minimum_count


def filter_usable_items(items: list[dict]) -> list[dict]:
    return [item for item in items if _is_usable_item(item)]


def build_signal_summary(items: list[dict]) -> dict[str, Any]:
    usable_items = filter_usable_items(items)
    return {
        "count": len(items),
        "usable_count": len(usable_items),
        "usable": bool(usable_items),
    }


def build_failure_state(
    *,
    kind: str,
    stage: str,
    provider: str,
    reason: str,
    retryable: bool,
    action_required: str,
    action_hint: str,
    verification_required: bool = False,
    verify_type: str = "",
    verify_uuid: str = "",
) -> dict[str, Any]:
    failure_state = {
        "kind": kind,
        "stage": stage,
        "provider": provider,
        "reason": reason,
        "retryable": retryable,
        "action_required": action_required,
        "action_hint": action_hint,
    }
    if verification_required:
        failure_state["verification_required"] = True
    if verify_type:
        failure_state["verify_type"] = verify_type
    if verify_uuid:
        failure_state["verify_uuid"] = verify_uuid
    return failure_state


def _is_usable_item(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("error"):
        return False
    title = str(item.get("title", "")).strip()
    return bool(title)
