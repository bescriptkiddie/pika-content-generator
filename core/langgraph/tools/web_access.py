"""Browser access wrapper with portable backend selection."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

PLAYWRIGHT_DEFAULT_PROFILE = str(Path.home() / ".pikaengine" / "playwright" / "xiaohongshu")
XHS_WEB_ACCESS_PROBE_URL = "https://creator.xiaohongshu.com/publish/publish"

_PLAYWRIGHT_RUNTIME: dict[str, Any] = {
    "playwright": None,
    "context": None,
    "pages": {},
    "config_key": None,
}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _config_str(config: dict[str, Any] | None, key: str, env_name: str, default: str) -> str:
    if config and key in config:
        value = str(config.get(key, "")).strip()
        if value:
            return value
    value = os.getenv(env_name, "").strip()
    return value or default


def _config_int(config: dict[str, Any] | None, key: str, env_name: str, default: int) -> int:
    if config and key in config:
        try:
            return int(config.get(key, default))
        except (TypeError, ValueError):
            return default
    return _env_int(env_name, default)


def _config_bool(config: dict[str, Any] | None, key: str, env_name: str, default: bool) -> bool:
    if config and key in config:
        value = str(config.get(key, "")).strip().lower()
        if not value:
            return default
        return value in {"1", "true", "yes", "on"}
    return _env_bool(env_name, default)


def browser_backend(config: dict[str, Any] | None = None) -> str:
    return _config_str(config, "browser_backend", "XHS_BROWSER_BACKEND", "playwright_persistent")


def browser_available(config: dict[str, Any] | None = None) -> bool:
    return browser_status(config).get("status") == "success"


def browser_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_status(config)
    return _playwright_status(config)


def browser_open_tab(url: str, wait_seconds: float = 2.0, config: dict[str, Any] | None = None) -> str | None:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_open_tab(url, wait_seconds=wait_seconds, config=config)
    return _playwright_open_tab(url, wait_seconds=wait_seconds, config=config)


def browser_eval(target_id: str, js: str, config: dict[str, Any] | None = None) -> str:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_eval(target_id, js, config=config)
    return _playwright_eval_action(target_id, js)


def browser_eval_json(target_id: str, js: str, config: dict[str, Any] | None = None) -> dict | list | None:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_eval_json(target_id, js, config=config)
    return _playwright_eval_json(target_id, js)


def browser_scroll(target_id: str, y: int = 3000, config: dict[str, Any] | None = None) -> None:
    backend = browser_backend(config)
    if backend == "cdp_http":
        _legacy_cdp_scroll(target_id, y=y, config=config)
        return
    _playwright_scroll(target_id, y=y)


def browser_click(target_id: str, selector: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_click(target_id, selector, config=config)
    return _playwright_click(target_id, selector)


def browser_fill(target_id: str, selector: str, value: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_fill(target_id, selector, value, config=config)
    return _playwright_fill(target_id, selector, value)


def browser_screenshot(target_id: str, file_path: str = "/tmp/screenshot.png", config: dict[str, Any] | None = None) -> str:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_screenshot(target_id, file_path=file_path, config=config)
    return _playwright_screenshot(target_id, file_path=file_path)


def browser_close_tab(target_id: str, config: dict[str, Any] | None = None) -> None:
    backend = browser_backend(config)
    if backend == "cdp_http":
        _legacy_cdp_close_tab(target_id, config=config)
        return
    _playwright_close_tab(target_id)


def browser_fetch_page(url: str, extract_js: str = "", config: dict[str, Any] | None = None) -> dict[str, Any]:
    target_id = None
    try:
        target_id = browser_open_tab(url, config=config)
        if not target_id:
            return {
                "error": "Failed to open browser tab",
                "url": url,
                "error_code": "unavailable",
                "action_required": browser_status(config).get("action_required", "start_provider"),
            }

        js = extract_js or _default_extract_js()
        result = browser_eval_json(target_id, js, config=config)
        if result is None:
            raw = _browser_eval_raw(target_id, js, config=config)
            return {"raw_text": raw, "url": url, "error_code": "parse_error"}
        return result
    except requests.Timeout:
        return {
            "error": "browser request timeout",
            "url": url,
            "error_code": "timeout",
            "action_required": "retry_later",
        }
    except Exception as exc:
        status = browser_status(config)
        if status.get("status") in {"unavailable", "auth_expired", "timeout", "error"}:
            return {
                "error": status.get("reason", str(exc)),
                "url": url,
                "error_code": status.get("status", "error"),
                "action_required": status.get("action_required", "retry_later"),
                "action_hint": status.get("action_hint", ""),
            }
        return {
            "error": str(exc),
            "url": url,
            "error_code": "error",
            "action_required": "retry_later",
        }
    finally:
        if target_id:
            browser_close_tab(target_id, config=config)


def _playwright_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        context = _get_playwright_context(config)
    except ModuleNotFoundError:
        return {
            "status": "unavailable",
            "reason": "playwright package not installed",
            "retryable": False,
            "action_required": "install_provider",
            "action_hint": "安装 playwright 并执行 playwright install chromium",
        }
    except Exception as exc:
        return _playwright_unavailable_status(exc)

    if not _has_xiaohongshu_cookie(context):
        return {
            "status": "auth_expired",
            "reason": "browser profile has no xiaohongshu login session",
            "retryable": False,
            "action_required": "reauth",
            "action_hint": "使用持久化浏览器 profile 手动登录小红书后重试",
        }
    return {
        "status": "success",
        "reason": "",
        "retryable": False,
        "action_required": "none",
        "action_hint": "",
    }


def _playwright_unavailable_status(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    action_required = "start_provider"
    action_hint = "检查浏览器配置后重试"
    if "Executable doesn't exist" in message or "playwright package not installed" in message:
        action_required = "install_provider"
        action_hint = "安装 playwright 并执行 playwright install chromium"
    elif "user data directory is already in use" in message or "SingletonLock" in message:
        action_required = "fix_config"
        action_hint = "关闭占用该 profile 的浏览器实例，或改用新的 XHS_PLAYWRIGHT_USER_DATA_DIR"
    elif "Timeout" in message or "timed out" in message:
        return {
            "status": "timeout",
            "reason": message,
            "retryable": True,
            "action_required": "retry_later",
            "action_hint": "稍后重试浏览器 provider",
        }
    return {
        "status": "unavailable",
        "reason": message,
        "retryable": True,
        "action_required": action_required,
        "action_hint": action_hint,
    }


def _playwright_user_data_dir(config: dict[str, Any] | None = None) -> str:
    return str(Path(_config_str(config, "user_data_dir", "XHS_PLAYWRIGHT_USER_DATA_DIR", PLAYWRIGHT_DEFAULT_PROFILE)).expanduser())


def _playwright_channel(config: dict[str, Any] | None = None) -> str:
    return _config_str(config, "playwright_channel", "XHS_PLAYWRIGHT_CHANNEL", "")


def _playwright_startup_timeout_ms(config: dict[str, Any] | None = None) -> int:
    return _config_int(config, "startup_timeout_ms", "XHS_BROWSER_STARTUP_TIMEOUT", 30000)


def _playwright_action_timeout_ms(config: dict[str, Any] | None = None) -> int:
    return _config_int(config, "action_timeout_ms", "XHS_BROWSER_ACTION_TIMEOUT", 15000)


def _playwright_navigation_timeout_ms(config: dict[str, Any] | None = None) -> int:
    return _config_int(config, "navigation_timeout_ms", "XHS_BROWSER_NAVIGATION_TIMEOUT", 30000)


def _playwright_runtime_key(config: dict[str, Any] | None = None) -> tuple[str, bool, str, int, int, int]:
    return (
        _playwright_user_data_dir(config),
        _config_bool(config, "headless", "XHS_PLAYWRIGHT_HEADLESS", False),
        _playwright_channel(config),
        _playwright_startup_timeout_ms(config),
        _playwright_action_timeout_ms(config),
        _playwright_navigation_timeout_ms(config),
    )


def _reset_playwright_runtime() -> None:
    pages = _PLAYWRIGHT_RUNTIME.get("pages", {})
    for page in list(pages.values()):
        try:
            page.close()
        except Exception:
            pass
    context = _PLAYWRIGHT_RUNTIME.get("context")
    if context is not None:
        try:
            context.close()
        except Exception:
            pass
    playwright = _PLAYWRIGHT_RUNTIME.get("playwright")
    if playwright is not None:
        try:
            playwright.stop()
        except Exception:
            pass
    _PLAYWRIGHT_RUNTIME["playwright"] = None
    _PLAYWRIGHT_RUNTIME["context"] = None
    _PLAYWRIGHT_RUNTIME["pages"] = {}
    _PLAYWRIGHT_RUNTIME["config_key"] = None


def _get_playwright_context(config: dict[str, Any] | None = None) -> Any:
    runtime_key = _playwright_runtime_key(config)
    context = _PLAYWRIGHT_RUNTIME.get("context")
    if context is not None and _PLAYWRIGHT_RUNTIME.get("config_key") == runtime_key:
        return context
    if context is not None and _PLAYWRIGHT_RUNTIME.get("config_key") != runtime_key:
        _reset_playwright_runtime()

    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    user_data_dir = _playwright_user_data_dir(config)
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    launch_kwargs: dict[str, Any] = {
        "headless": _config_bool(config, "headless", "XHS_PLAYWRIGHT_HEADLESS", False),
        "viewport": {"width": 1440, "height": 960},
        "timeout": _playwright_startup_timeout_ms(config),
    }
    channel = _playwright_channel(config)
    if channel:
        launch_kwargs["channel"] = channel

    context = playwright.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
    context.set_default_timeout(_playwright_action_timeout_ms(config))
    context.set_default_navigation_timeout(_playwright_navigation_timeout_ms(config))

    _PLAYWRIGHT_RUNTIME["playwright"] = playwright
    _PLAYWRIGHT_RUNTIME["context"] = context
    _PLAYWRIGHT_RUNTIME["pages"] = {}
    _PLAYWRIGHT_RUNTIME["config_key"] = runtime_key
    return context


def _has_xiaohongshu_cookie(context: Any) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    return any("xiaohongshu.com" in str(cookie.get("domain", "")) for cookie in cookies)


def _playwright_open_tab(url: str, wait_seconds: float = 2.0, config: dict[str, Any] | None = None) -> str | None:
    page = None
    try:
        context = _get_playwright_context(config)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=_playwright_navigation_timeout_ms(config))
        if wait_seconds > 0:
            page.wait_for_timeout(int(wait_seconds * 1000))
        target_id = uuid.uuid4().hex
        _PLAYWRIGHT_RUNTIME.setdefault("pages", {})[target_id] = page
        return target_id
    except Exception:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        return None


def _get_playwright_page(target_id: str) -> Any:
    page = _PLAYWRIGHT_RUNTIME.get("pages", {}).get(target_id)
    if page is None:
        raise KeyError(f"Unknown browser target: {target_id}")
    return page


def _browser_eval_raw(target_id: str, js: str, config: dict[str, Any] | None = None) -> str:
    backend = browser_backend(config)
    if backend == "cdp_http":
        return _legacy_cdp_eval(target_id, js, config=config)
    return _playwright_eval_raw(target_id, js)


def _playwright_eval_raw(target_id: str, js: str) -> str:
    page = _get_playwright_page(target_id)
    result = page.evaluate(js)
    if result is None:
        return ""
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _playwright_eval_action(target_id: str, js: str) -> str:
    page = _get_playwright_page(target_id)
    page.evaluate(f"() => {{{js}\nreturn null;}}")
    return ""


def _playwright_eval_json(target_id: str, js: str) -> dict | list | None:
    page = _get_playwright_page(target_id)
    result = page.evaluate(js)
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    return None


def _playwright_scroll(target_id: str, y: int = 3000) -> None:
    page = _get_playwright_page(target_id)
    page.mouse.wheel(0, y)
    page.wait_for_timeout(500)


def _playwright_click(target_id: str, selector: str) -> dict[str, Any]:
    page = _get_playwright_page(target_id)
    page.locator(selector).first.click(timeout=page.context._timeout_settings.timeout())
    return {"status": "clicked", "selector": selector}


def _playwright_fill(target_id: str, selector: str, value: str) -> dict[str, Any]:
    page = _get_playwright_page(target_id)
    page.locator(selector).first.fill(value, timeout=page.context._timeout_settings.timeout())
    return {"status": "filled", "selector": selector}


def _playwright_screenshot(target_id: str, file_path: str = "/tmp/screenshot.png") -> str:
    page = _get_playwright_page(target_id)
    page.screenshot(path=file_path, full_page=True)
    return file_path


def _playwright_close_tab(target_id: str) -> None:
    page = _PLAYWRIGHT_RUNTIME.get("pages", {}).pop(target_id, None)
    if page is None:
        return
    try:
        page.close()
    except Exception:
        pass


def _cdp_base(config: dict[str, Any] | None = None) -> str:
    return _config_str(
        config,
        "cdp_base",
        "XHS_WEB_ACCESS_BASE",
        os.getenv("CDP_BASE", "http://localhost:3456").strip() or "http://localhost:3456",
    )


def _cdp_timeout(config: dict[str, Any] | None = None) -> int:
    return _config_int(config, "browser_request_timeout", "XHS_BROWSER_REQUEST_TIMEOUT", 20)


def _legacy_cdp_available(config: dict[str, Any] | None = None) -> bool:
    try:
        resp = requests.get(f"{_cdp_base(config)}/targets", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _legacy_cdp_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        resp = requests.get(f"{_cdp_base(config)}/targets", timeout=3)
    except requests.Timeout:
        return {
            "status": "timeout",
            "reason": "web-access CDP proxy request timeout",
            "retryable": True,
            "action_required": "retry_later",
            "action_hint": "稍后重试本地 CDP / 浏览器代理服务",
        }
    except Exception:
        return {
            "status": "unavailable",
            "reason": "web-access CDP proxy not running",
            "retryable": True,
            "action_required": "start_provider",
            "action_hint": "启动本地 CDP / 浏览器代理服务",
        }

    if resp.status_code != 200:
        return {
            "status": "error",
            "reason": f"web-access CDP proxy returned HTTP {resp.status_code}",
            "retryable": True,
            "action_required": "fix_config",
            "action_hint": "检查 web-access 代理地址与本地 Chrome 调试连接",
        }

    target_id = None
    try:
        target_id = _legacy_cdp_open_tab(XHS_WEB_ACCESS_PROBE_URL, wait_seconds=1.0, config=config)
        if not target_id:
            return {
                "status": "error",
                "reason": "web-access CDP proxy could not open xiaohongshu probe page",
                "retryable": True,
                "action_required": "fix_config",
                "action_hint": "检查 web-access 代理是否已连接到本地 Chrome",
            }
        probe = _legacy_cdp_eval_json(target_id, _xiaohongshu_login_probe_js(), config=config)
        if not isinstance(probe, dict):
            return {
                "status": "error",
                "reason": "web-access CDP probe returned invalid response",
                "retryable": True,
                "action_required": "retry_later",
                "action_hint": "稍后重试本地浏览器探测",
            }
        if probe.get("logged_in"):
            return {
                "status": "success",
                "reason": "",
                "retryable": False,
                "action_required": "none",
                "action_hint": "",
            }
        return {
            "status": "auth_expired",
            "reason": "local Chrome has no active xiaohongshu login session",
            "retryable": False,
            "action_required": "reauth",
            "action_hint": "先在本地 Chrome 完成小红书登录，再重试采集",
        }
    except requests.Timeout:
        return {
            "status": "timeout",
            "reason": "web-access CDP probe timeout",
            "retryable": True,
            "action_required": "retry_later",
            "action_hint": "稍后重试本地浏览器探测",
        }
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "retryable": True,
            "action_required": "fix_config",
            "action_hint": "检查 web-access 代理、Chrome 调试端口和页面访问状态",
        }
    finally:
        if target_id:
            _legacy_cdp_close_tab(target_id, config=config)


def _legacy_cdp_open_tab(url: str, wait_seconds: float = 2.0, config: dict[str, Any] | None = None) -> str | None:
    try:
        resp = requests.get(
            f"{_cdp_base(config)}/new",
            params={"url": url},
            timeout=_cdp_timeout(config),
        )
        target_id = resp.json().get("targetId")
        if target_id and wait_seconds > 0:
            time.sleep(wait_seconds)
        return target_id
    except Exception:
        return None


def _legacy_cdp_eval(target_id: str, js: str, config: dict[str, Any] | None = None) -> str:
    resp = requests.post(
        f"{_cdp_base(config)}/eval",
        params={"target": target_id},
        data=js.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=_cdp_timeout(config),
    )
    return resp.text


def _legacy_cdp_eval_json(target_id: str, js: str, config: dict[str, Any] | None = None) -> dict | list | None:
    raw = _legacy_cdp_eval(target_id, js, config=config)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict) and "value" in parsed:
        value = parsed.get("value")
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                inner = json.loads(value)
                if isinstance(inner, (dict, list)):
                    return inner
            except json.JSONDecodeError:
                return None
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def _legacy_cdp_scroll(target_id: str, y: int = 3000, config: dict[str, Any] | None = None) -> None:
    try:
        requests.get(
            f"{_cdp_base(config)}/scroll",
            params={"target": target_id, "y": y},
            timeout=_cdp_timeout(config),
        )
    except Exception:
        pass


def _legacy_cdp_click(target_id: str, selector: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    requests.post(
        f"{_cdp_base(config)}/click",
        params={"target": target_id},
        data=selector.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=_cdp_timeout(config),
    )
    return {"status": "clicked", "selector": selector}


def _legacy_cdp_fill(target_id: str, selector: str, value: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    js = f'document.querySelector({json.dumps(selector)}).value = {json.dumps(value)}'
    _legacy_cdp_eval(target_id, js, config=config)
    return {"status": "filled", "selector": selector}


def _legacy_cdp_screenshot(target_id: str, file_path: str = "/tmp/screenshot.png", config: dict[str, Any] | None = None) -> str:
    try:
        requests.get(
            f"{_cdp_base(config)}/screenshot",
            params={"target": target_id, "file": file_path},
            timeout=_cdp_timeout(config),
        )
        return file_path
    except Exception:
        return ""


def _legacy_cdp_close_tab(target_id: str, config: dict[str, Any] | None = None) -> None:
    try:
        requests.get(
            f"{_cdp_base(config)}/close",
            params={"target": target_id},
            timeout=5,
        )
    except Exception:
        pass


cdp_available = browser_available
cdp_status = browser_status
cdp_open_tab = browser_open_tab
cdp_eval = browser_eval
cdp_eval_json = browser_eval_json
cdp_scroll = browser_scroll
cdp_click = browser_click
cdp_fill = browser_fill
cdp_screenshot = browser_screenshot
cdp_close_tab = browser_close_tab
cdp_fetch_page = browser_fetch_page


def _xiaohongshu_login_probe_js() -> str:
    return """(() => {
        const cookie = document.cookie || '';
        const href = location.href || '';
        const text = document.body?.innerText || '';
        const hasA1 = /(^|; )a1=/.test(cookie);
        const hasWebSession = /(^|; )web_session=/.test(cookie);
        const hasXsecappid = /(^|; )xsecappid=/.test(cookie);
        const creatorSignals = [
            '[placeholder*="标题"]',
            '#post-title',
            '.ql-editor',
            '.ProseMirror',
        ].some((selector) => Boolean(document.querySelector(selector)));
        const creatorLoginRedirect = href.includes('creator.xiaohongshu.com/login');
        const loginHints = /(登录|注册|扫码登录|手机号登录|验证码登录)/.test(text);
        const siteLoggedIn = hasA1 && hasXsecappid;
        const creatorReady = creatorSignals || (siteLoggedIn && !creatorLoginRedirect);
        return JSON.stringify({
            logged_in: siteLoggedIn || creatorReady,
            site_logged_in: siteLoggedIn,
            creator_ready: creatorReady,
            creator_login_redirect: creatorLoginRedirect,
            has_a1: hasA1,
            has_web_session: hasWebSession,
            has_xsecappid: hasXsecappid,
            login_hints: loginHints,
            url: href,
        });
    })()"""


def _default_extract_js() -> str:
    return """JSON.stringify({
        title: document.title,
        url: location.href,
        text: document.body?.innerText?.substring(0, 3000) || '',
        meta_description: document.querySelector('meta[name=description]')?.content || ''
    })"""
