"""web-access CDP wrapper — controls real Chrome with login state"""

import json
import time
import requests

CDP_BASE = "http://localhost:3456"
CDP_TIMEOUT = 20


def cdp_available() -> bool:
    """Check if web-access CDP proxy is running."""
    try:
        resp = requests.get(f"{CDP_BASE}/targets", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def cdp_open_tab(url: str, wait_seconds: float = 2.0) -> str | None:
    """Open URL in a new Chrome tab, return targetId."""
    try:
        resp = requests.get(
            f"{CDP_BASE}/new",
            params={"url": url},
            timeout=CDP_TIMEOUT,
        )
        target_id = resp.json().get("targetId")
        if target_id and wait_seconds > 0:
            time.sleep(wait_seconds)
        return target_id
    except Exception:
        return None


def cdp_eval(target_id: str, js: str) -> str:
    """Execute JS in a tab and return raw response text."""
    resp = requests.post(
        f"{CDP_BASE}/eval",
        params={"target": target_id},
        data=js,
        timeout=CDP_TIMEOUT,
    )
    return resp.text


def cdp_eval_json(target_id: str, js: str) -> dict | list | None:
    """Execute JS and parse as JSON."""
    raw = cdp_eval(target_id, js)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cdp_scroll(target_id: str, y: int = 3000) -> None:
    """Scroll page to trigger lazy loading."""
    try:
        requests.get(
            f"{CDP_BASE}/scroll",
            params={"target": target_id, "y": y},
            timeout=CDP_TIMEOUT,
        )
    except Exception:
        pass


def cdp_click(target_id: str, selector: str) -> dict:
    """Click an element via CDP."""
    requests.post(
        f"{CDP_BASE}/click",
        params={"target": target_id},
        data=selector,
        timeout=CDP_TIMEOUT,
    )
    return {"status": "clicked", "selector": selector}


def cdp_fill(target_id: str, selector: str, value: str) -> dict:
    """Fill an input field via CDP eval."""
    js = f'document.querySelector({json.dumps(selector)}).value = {json.dumps(value)}'
    cdp_eval(target_id, js)
    return {"status": "filled", "selector": selector}


def cdp_screenshot(target_id: str, file_path: str = "/tmp/screenshot.png") -> str:
    """Capture screenshot of a tab."""
    try:
        requests.get(
            f"{CDP_BASE}/screenshot",
            params={"target": target_id, "file": file_path},
            timeout=CDP_TIMEOUT,
        )
        return file_path
    except Exception:
        return ""


def cdp_close_tab(target_id: str) -> None:
    """Close a browser tab."""
    try:
        requests.get(
            f"{CDP_BASE}/close",
            params={"target": target_id},
            timeout=5,
        )
    except Exception:
        pass


def cdp_fetch_page(url: str, extract_js: str = "") -> dict:
    """Open URL in real Chrome and extract data. Closes tab after.

    Args:
        url: Target URL to open
        extract_js: Optional JS for extraction. Default extracts title+text.
    """
    target_id = None
    try:
        target_id = cdp_open_tab(url)
        if not target_id:
            return {"error": "Failed to open tab", "url": url}

        js = extract_js or _default_extract_js()
        result = cdp_eval_json(target_id, js)

        if result is None:
            raw = cdp_eval(target_id, js)
            return {"raw_text": raw, "url": url}

        return result

    except requests.ConnectionError:
        return {"error": "web-access CDP not running. Enable Chrome remote debugging."}
    except requests.Timeout:
        return {"error": "CDP timeout", "url": url}
    finally:
        if target_id:
            cdp_close_tab(target_id)


def _default_extract_js() -> str:
    return """JSON.stringify({
        title: document.title,
        url: location.href,
        text: document.body?.innerText?.substring(0, 3000) || '',
        meta_description: document.querySelector('meta[name=description]')?.content || ''
    })"""
