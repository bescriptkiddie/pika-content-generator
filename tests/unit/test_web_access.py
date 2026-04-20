from __future__ import annotations

from typing import Any

from core.langgraph.tools import web_access


class _FakeContext:
    def __init__(self, cookies: list[dict[str, Any]]):
        self._cookies = cookies

    def cookies(self) -> list[dict[str, Any]]:
        return self._cookies


class _Boom(Exception):
    pass


SUCCESS_STATUS = {
    "status": "success",
    "reason": "",
    "retryable": False,
    "action_required": "none",
    "action_hint": "",
}


UNAVAILABLE_STATUS = {
    "status": "unavailable",
    "reason": "web-access CDP proxy not running",
    "retryable": True,
    "action_required": "start_provider",
    "action_hint": "启动本地 CDP / 浏览器代理服务",
}


def test_browser_backend_defaults_to_playwright(monkeypatch) -> None:
    monkeypatch.delenv("XHS_BROWSER_BACKEND", raising=False)

    assert web_access.browser_backend({}) == "playwright_persistent"


def test_browser_status_uses_playwright_backend_by_default(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake_playwright_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
        seen["config"] = config
        return SUCCESS_STATUS

    def fail_legacy(config: dict[str, Any] | None = None) -> dict[str, Any]:
        raise AssertionError("legacy backend should not be used")

    monkeypatch.setattr(web_access, "_playwright_status", fake_playwright_status)
    monkeypatch.setattr(web_access, "_legacy_cdp_status", fail_legacy)

    status = web_access.browser_status({"user_data_dir": "/tmp/pika-profile"})

    assert status == SUCCESS_STATUS
    assert seen["config"]["user_data_dir"] == "/tmp/pika-profile"


def test_browser_status_uses_legacy_cdp_backend_when_requested(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake_legacy_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
        seen["config"] = config
        return UNAVAILABLE_STATUS

    def fail_playwright(config: dict[str, Any] | None = None) -> dict[str, Any]:
        raise AssertionError("playwright backend should not be used")

    monkeypatch.setattr(web_access, "_legacy_cdp_status", fake_legacy_status)
    monkeypatch.setattr(web_access, "_playwright_status", fail_playwright)

    status = web_access.browser_status({"browser_backend": "cdp_http", "cdp_base": "http://127.0.0.1:3456"})

    assert status == UNAVAILABLE_STATUS
    assert seen["config"]["cdp_base"] == "http://127.0.0.1:3456"


def test_playwright_status_returns_auth_expired_without_xiaohongshu_cookie(monkeypatch) -> None:
    monkeypatch.setattr(web_access, "_get_playwright_context", lambda config=None: _FakeContext([]))

    status = web_access._playwright_status({"user_data_dir": "/tmp/pika-profile"})

    assert status["status"] == "auth_expired"
    assert status["action_required"] == "reauth"


def test_playwright_status_returns_success_with_xiaohongshu_cookie(monkeypatch) -> None:
    cookies = [{"domain": ".xiaohongshu.com", "name": "a1", "value": "cookie"}]
    monkeypatch.setattr(web_access, "_get_playwright_context", lambda config=None: _FakeContext(cookies))

    status = web_access._playwright_status({"user_data_dir": "/tmp/pika-profile"})

    assert status == SUCCESS_STATUS


def test_playwright_status_maps_timeout_to_retry_later(monkeypatch) -> None:
    def boom(config: dict[str, Any] | None = None) -> Any:
        raise _Boom("Timeout 30000ms exceeded while launching browser")

    monkeypatch.setattr(web_access, "_get_playwright_context", boom)

    status = web_access._playwright_status({"user_data_dir": "/tmp/pika-profile"})

    assert status["status"] == "timeout"
    assert status["retryable"] is True
    assert status["action_required"] == "retry_later"
