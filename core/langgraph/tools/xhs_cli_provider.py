from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

VERIFY_TYPE_PATTERN = re.compile(r"verify_type=(\d{1,8})")
VERIFY_UUID_PATTERN = re.compile(r"verify_uuid=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def _configured_module_path() -> str:
    return os.getenv("XHS_CLI_MODULE_PATH", "").strip()


def _append_module_path(module_path: str) -> None:
    resolved = str(Path(module_path).expanduser().resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _load_xhs_cli() -> tuple[bool, Any, Any, Any, Any, Any]:
    module_path = _configured_module_path()
    if module_path:
        try:
            _append_module_path(module_path)
        except Exception:
            return False, None, None, None, None, None
    try:
        from xhs_cli.auth import get_cookie_string, cookie_str_to_dict
        from xhs_cli.client import XhsClient
        from xhs_cli.exceptions import DataFetchError, LoginError
        return True, get_cookie_string, cookie_str_to_dict, XhsClient, DataFetchError, LoginError
    except Exception:
        return False, None, None, None, None, None


def xhs_cli_status() -> dict[str, Any]:
    ok, get_cookie_string, _, _, _, _ = _load_xhs_cli()
    if not ok:
        return {
            "status": "unavailable",
            "reason": "xhs-cli package not importable in current runtime",
            "retryable": False,
            "action_required": "install_provider",
            "action_hint": "将 xhs-cli 安装为依赖，或通过 XHS_CLI_MODULE_PATH 指向本地模块路径",
        }
    cookie = get_cookie_string()
    if not cookie:
        return {
            "status": "auth_expired",
            "reason": "xhs-cli has no valid cookie session",
            "retryable": False,
            "action_required": "reauth",
            "action_hint": "运行 xhs login 重新登录小红书",
        }
    return {
        "status": "success",
        "reason": "",
        "retryable": False,
        "action_required": "none",
        "action_hint": "",
    }


def search_notes(keyword: str, *, max_notes: int = 10) -> list[dict]:
    ok, get_cookie_string, cookie_str_to_dict, XhsClient, DataFetchError, LoginError = _load_xhs_cli()
    if not ok:
        return [_error_item("unavailable", "xhs-cli package not importable in current runtime")]
    cookie = get_cookie_string()
    if not cookie:
        return [_error_item("auth_expired", "xhs-cli has no valid cookie session")]
    try:
        with XhsClient(cookie_str_to_dict(cookie)) as client:
            results = client.search_notes(keyword)
        return _normalize_note_list(results, max_notes=max_notes, source_type="keyword_search")
    except LoginError as exc:
        return [_login_error_item(exc)]
    except DataFetchError as exc:
        return [_error_item("error", str(exc), retryable=True, action_required="retry_later", action_hint="稍后重试 xhs-cli provider")]


def fetch_feed(*, max_notes: int = 20) -> list[dict]:
    ok, get_cookie_string, cookie_str_to_dict, XhsClient, DataFetchError, LoginError = _load_xhs_cli()
    if not ok:
        return [_error_item("unavailable", "xhs-cli package not importable in current runtime")]
    cookie = get_cookie_string()
    if not cookie:
        return [_error_item("auth_expired", "xhs-cli has no valid cookie session")]
    try:
        with XhsClient(cookie_str_to_dict(cookie)) as client:
            results = client.get_feed()
        return _normalize_note_list(results, max_notes=max_notes, source_type="feed")
    except LoginError as exc:
        return [_login_error_item(exc)]
    except DataFetchError as exc:
        return [_error_item("error", str(exc), retryable=True, action_required="retry_later", action_hint="稍后重试 xhs-cli provider")]


def fetch_note_detail(note_id: str, *, xsec_token: str = "") -> dict[str, Any]:
    ok, get_cookie_string, cookie_str_to_dict, XhsClient, DataFetchError, LoginError = _load_xhs_cli()
    if not ok:
        return _error_item("unavailable", "xhs-cli package not importable in current runtime")
    cookie = get_cookie_string()
    if not cookie:
        return _error_item("auth_expired", "xhs-cli has no valid cookie session")
    try:
        with XhsClient(cookie_str_to_dict(cookie)) as client:
            detail = client.get_note_detail(note_id, xsec_token=xsec_token)
        return detail if isinstance(detail, dict) else {}
    except LoginError as exc:
        return _login_error_item(exc)
    except DataFetchError as exc:
        return _error_item("error", str(exc), retryable=True, action_required="retry_later", action_hint="稍后重试 xhs-cli provider")


def publish_note(*, title: str, body: str, images: list[str] | None = None) -> dict[str, Any]:
    ok, get_cookie_string, cookie_str_to_dict, XhsClient, _, LoginError = _load_xhs_cli()
    if not ok:
        return _error_item("unavailable", "xhs-cli package not importable in current runtime")
    cookie = get_cookie_string()
    if not cookie:
        return _error_item("auth_expired", "xhs-cli has no valid cookie session")
    try:
        with XhsClient(cookie_str_to_dict(cookie)) as client:
            result = client.publish_note(title=title, content=body, image_paths=images or [])
        return result if isinstance(result, dict) else {"status": "published"}
    except LoginError as exc:
        return _login_error_item(exc)
    except Exception as exc:
        return _error_item("error", str(exc), retryable=True, action_required="retry_later", action_hint="稍后重试 xhs-cli provider")


def _normalize_note_list(items: list[dict], *, max_notes: int, source_type: str) -> list[dict]:
    normalized: list[dict] = []
    for item in items[:max_notes]:
        if not isinstance(item, dict):
            continue
        note_id = str(item.get("id", "") or item.get("noteId", "") or item.get("note_id", ""))
        title = str(item.get("title", "") or item.get("display_title", "") or item.get("note_card", {}).get("display_title", "")).strip()
        user = item.get("user", {}) if isinstance(item.get("user", {}), dict) else {}
        interact = item.get("interact_info", {}) if isinstance(item.get("interact_info", {}), dict) else {}
        xsec_token = str(item.get("xsec_token", "") or item.get("xsecToken", ""))
        if not title:
            continue
        normalized.append({
            "id": note_id,
            "title": title,
            "author": user.get("nickname", item.get("author", "")),
            "likes": interact.get("liked_count", item.get("likes", "0")),
            "url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else item.get("url", ""),
            "xsec_token": xsec_token,
            "source": "xhs-cli",
            "source_platform": "xiaohongshu",
            "source_type": source_type,
        })
    return normalized


def _login_error_item(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    verify_type = _extract_verify_type(message)
    verify_uuid = _extract_verify_uuid(message)
    if "requires verification" in message or "Blocked by security verification" in message or verify_type or verify_uuid:
        return _error_item(
            "verification_required",
            "xhs-cli QR login requires platform verification",
            retryable=False,
            action_required="verify",
            action_hint="按平台要求完成验证后重新执行 xhs login --qrcode",
            verification_required=True,
            verify_type=verify_type,
            verify_uuid=verify_uuid,
        )
    return _error_item(
        "auth_expired",
        message or "xhs-cli login expired",
        retryable=False,
        action_required="reauth",
        action_hint="运行 xhs login 重新登录小红书",
    )


def _error_item(
    status: str,
    reason: str,
    *,
    retryable: bool = False,
    action_required: str | None = None,
    action_hint: str = "",
    verification_required: bool = False,
    verify_type: str = "",
    verify_uuid: str = "",
) -> dict[str, Any]:
    item = {
        "error": reason,
        "error_code": status,
        "retryable": retryable,
        "action_required": action_required or _default_action_required(status),
        "action_hint": action_hint or _default_action_hint(status),
        "verification_required": verification_required,
    }
    if verify_type:
        item["verify_type"] = verify_type
    if verify_uuid:
        item["verify_uuid"] = verify_uuid
    return item


def _default_action_required(status: str) -> str:
    if status == "unavailable":
        return "install_provider"
    if status == "auth_expired":
        return "reauth"
    if status == "verification_required":
        return "verify"
    if status in {"timeout", "error"}:
        return "retry_later"
    return "none"


def _default_action_hint(status: str) -> str:
    if status == "unavailable":
        return "将 xhs-cli 安装为依赖，或通过 XHS_CLI_MODULE_PATH 指向本地模块路径"
    if status == "auth_expired":
        return "运行 xhs login 重新登录小红书"
    if status == "verification_required":
        return "按平台要求完成验证后重新执行 xhs login --qrcode"
    if status in {"timeout", "error"}:
        return "稍后重试 xhs-cli provider"
    return ""


def _extract_verify_type(message: str) -> str:
    match = VERIFY_TYPE_PATTERN.search(message)
    return match.group(1) if match else ""


def _extract_verify_uuid(message: str) -> str:
    match = VERIFY_UUID_PATTERN.search(message)
    return match.group(1).lower() if match else ""
