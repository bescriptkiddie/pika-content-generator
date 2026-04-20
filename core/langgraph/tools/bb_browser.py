"""bb-browser CLI wrapper — 103 platform commands, public data"""

from __future__ import annotations

import json
import subprocess
from typing import Any


def bb_browser_site(command: str, *, timeout: int = 60) -> list[dict]:
    """Run a bb-browser site command and return parsed JSON output."""
    parts = command.split()
    cmd = ["bb-browser", "site"] + parts

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            return [{"error": result.stderr.strip(), "command": command, "error_code": "provider_error"}]

        output = result.stdout.strip()
        if not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return [{"text": line} for line in output.splitlines() if line.strip()]

    except subprocess.TimeoutExpired:
        return [{"error": "timeout", "command": command, "error_code": "timeout"}]
    except FileNotFoundError:
        return [{"error": "bb-browser not installed. Run: npm install -g bb-browser", "error_code": "unavailable"}]


def bb_browser_provider_status(command: str, *, timeout: int = 60) -> dict[str, Any]:
    items = bb_browser_site(command, timeout=timeout)
    if items and items[0].get("error_code") == "unavailable":
        return _status("unavailable", reason=items[0].get("error", "bb-browser unavailable"), retryable=False, action_required="install_provider", action_hint="安装并配置 bb-browser")
    if items and items[0].get("error_code") == "timeout":
        return _status("timeout", reason="bb-browser request timeout", retryable=True, action_required="retry_later", action_hint="稍后重试或降低采集规模")
    if items and items[0].get("error"):
        return _status("error", reason=items[0].get("error", "bb-browser error"), retryable=True, action_required="retry_later", action_hint="检查 bb-browser 命令与目标站点状态")
    if not items:
        return _status("empty", reason="bb-browser returned empty result", retryable=True, action_required="none", action_hint="")
    return _status("success", reason="", retryable=False, action_required="none", action_hint="")


def _status(status: str, *, reason: str, retryable: bool, action_required: str, action_hint: str) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "retryable": retryable,
        "action_required": action_required,
        "action_hint": action_hint,
    }
