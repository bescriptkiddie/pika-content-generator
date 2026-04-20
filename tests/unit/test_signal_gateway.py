from __future__ import annotations

from typing import Any

import pytest

from core.langgraph.tools import signal_gateway


def _success_item(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "author": "pika",
        "likes": 1,
        "url": "https://www.xiaohongshu.com/explore/demo",
        "source": "browser",
        "source_platform": "xiaohongshu",
        "source_type": "keyword_search",
    }


@pytest.mark.parametrize(
    ("provider_name", "expected_trace"),
    [
        ("browser_search", "browser:search:AI工具"),
        ("cdp_search", "cdp:search:AI工具"),
    ],
)
def test_search_provider_aliases_keep_trace_names(monkeypatch, provider_name: str, expected_trace: str) -> None:
    seen: dict[str, Any] = {}

    def fake_browser_search(keyword: str, max_notes: int = 10, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        seen["config"] = config
        return [_success_item(f"{keyword} 爆款")]

    monkeypatch.setattr(signal_gateway, "search_notes_by_keyword", fake_browser_search)

    result = signal_gateway.acquire_xiaohongshu_signals(
        {
            "mode": "search",
            "keywords": ["AI工具"],
            "max_per_keyword": 3,
            "browser_backend": "playwright_persistent",
            "provider_order": {
                "search": [provider_name],
                "feed": ["browser_feed"],
                "cross_platform": ["hosted_cross_platform"],
            },
        }
    )

    assert result["usable"] is True
    assert result["provider_trace"][0]["provider"] == expected_trace
    assert seen["config"]["browser_backend"] == "playwright_persistent"


@pytest.mark.parametrize(
    ("provider_name", "expected_trace"),
    [
        ("browser_feed", "browser:feed"),
        ("cdp_feed", "cdp:feed"),
        ("cdp_explore", "cdp:feed"),
    ],
)
def test_feed_provider_aliases_keep_trace_names(monkeypatch, provider_name: str, expected_trace: str) -> None:
    monkeypatch.setattr(
        signal_gateway,
        "fetch_explore_feed",
        lambda max_notes=20, config=None: [_success_item("今日趋势")],
    )
    monkeypatch.setattr(signal_gateway, "fetch_cross_platform_trending", lambda platforms, config=None: [])

    result = signal_gateway.acquire_xiaohongshu_signals(
        {
            "mode": "trending",
            "keywords": [],
            "cross_platforms": [],
            "provider_order": {
                "search": [],
                "feed": [provider_name],
                "cross_platform": [],
            },
        }
    )

    assert result["provider_trace"][0]["provider"] == expected_trace
    assert result["provider_trace"][0]["status"] == "success"


def test_browser_provider_uses_browser_status_when_search_returns_empty(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    monkeypatch.setattr(signal_gateway, "search_notes_by_keyword", lambda keyword, max_notes=10, config=None: [])

    def fake_browser_status(config: dict[str, Any]) -> dict[str, Any]:
        seen["config"] = config
        return {
            "status": "auth_expired",
            "reason": "browser profile has no xiaohongshu login session",
            "retryable": False,
            "action_required": "reauth",
            "action_hint": "使用持久化浏览器 profile 手动登录小红书后重试",
        }

    monkeypatch.setattr(signal_gateway, "browser_status", fake_browser_status)

    result = signal_gateway.acquire_xiaohongshu_signals(
        {
            "mode": "search",
            "keywords": ["AI工具"],
            "browser_backend": "playwright_persistent",
            "user_data_dir": "~/.pikaengine/playwright/xiaohongshu",
            "provider_order": {
                "search": ["browser_search"],
                "feed": ["browser_feed"],
                "cross_platform": ["hosted_cross_platform"],
            },
        }
    )

    assert result["usable"] is False
    assert result["failure_state"]["kind"] == "auth_expired"
    assert result["action_required"] == "reauth"
    assert result["provider_trace"][0]["provider"] == "browser:search:AI工具"
    assert seen["config"]["user_data_dir"] == "~/.pikaengine/playwright/xiaohongshu"
