from __future__ import annotations

from typing import Any

import requests

from core.langgraph.tools import web_access


class _FakeContext:
    def __init__(self, cookies: list[dict[str, Any]]):
        self._cookies = cookies

    def cookies(self) -> list[dict[str, Any]]:
        return self._cookies


class _Boom(Exception):
    pass


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


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


def test_cdp_status_returns_unavailable_when_proxy_is_down(monkeypatch) -> None:
    def boom(url: str, timeout: int = 3, **kwargs) -> Any:
        raise requests.ConnectionError("down")

    monkeypatch.setattr(web_access.requests, "get", boom)

    status = web_access._legacy_cdp_status({"cdp_base": "http://127.0.0.1:3456"})

    assert status["status"] == "unavailable"
    assert status["action_required"] == "start_provider"


def test_cdp_status_returns_auth_expired_when_probe_shows_logged_out(monkeypatch) -> None:
    monkeypatch.setattr(web_access.requests, "get", lambda url, timeout=3, **kwargs: _FakeResponse(200))
    monkeypatch.setattr(web_access, "_legacy_cdp_open_tab", lambda url, wait_seconds=1.0, config=None: "tab-1")
    monkeypatch.setattr(
        web_access,
        "_legacy_cdp_eval_json",
        lambda target_id, js, config=None: {"logged_in": False, "login_hints": True},
    )
    monkeypatch.setattr(web_access, "_legacy_cdp_close_tab", lambda target_id, config=None: None)

    status = web_access._legacy_cdp_status({"cdp_base": "http://127.0.0.1:3456"})

    assert status["status"] == "auth_expired"
    assert status["action_required"] == "reauth"


def test_cdp_status_returns_success_when_probe_shows_logged_in(monkeypatch) -> None:
    monkeypatch.setattr(web_access.requests, "get", lambda url, timeout=3, **kwargs: _FakeResponse(200))
    monkeypatch.setattr(web_access, "_legacy_cdp_open_tab", lambda url, wait_seconds=1.0, config=None: "tab-1")
    monkeypatch.setattr(
        web_access,
        "_legacy_cdp_eval_json",
        lambda target_id, js, config=None: {"logged_in": True, "has_cookie": True},
    )
    monkeypatch.setattr(web_access, "_legacy_cdp_close_tab", lambda target_id, config=None: None)

    status = web_access._legacy_cdp_status({"cdp_base": "http://127.0.0.1:3456"})

    assert status == SUCCESS_STATUS


def test_cdp_status_maps_probe_timeout(monkeypatch) -> None:
    monkeypatch.setattr(web_access.requests, "get", lambda url, timeout=3, **kwargs: _FakeResponse(200))
    monkeypatch.setattr(web_access, "_legacy_cdp_open_tab", lambda url, wait_seconds=1.0, config=None: "tab-1")

    def timeout_probe(target_id: str, js: str, config: dict[str, Any] | None = None) -> Any:
        raise requests.Timeout("timeout")

    monkeypatch.setattr(web_access, "_legacy_cdp_eval_json", timeout_probe)
    monkeypatch.setattr(web_access, "_legacy_cdp_close_tab", lambda target_id, config=None: None)

    status = web_access._legacy_cdp_status({"cdp_base": "http://127.0.0.1:3456"})

    assert status["status"] == "timeout"
    assert status["action_required"] == "retry_later"


def test_cdp_base_prefers_web_access_env(monkeypatch) -> None:
    monkeypatch.setenv("XHS_WEB_ACCESS_BASE", "http://127.0.0.1:4567")
    monkeypatch.setenv("CDP_BASE", "http://127.0.0.1:3456")

    assert web_access._cdp_base({}) == "http://127.0.0.1:4567"
