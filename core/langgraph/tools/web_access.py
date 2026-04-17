"""web-access CDP wrapper — controls real Chrome with login state"""

import json
import requests

CDP_BASE = "http://localhost:3456"
CDP_TIMEOUT = 15


def cdp_fetch_page(url: str, extract_js: str = "") -> dict:
    """Open URL in real Chrome (with login state) and extract data.

    Args:
        url: Target URL to open
        extract_js: Optional JS to run for data extraction.
                    If empty, returns page title and text content.
    """
    target_id = None

    try:
        # Open new tab
        resp = requests.get(
            f"{CDP_BASE}/new",
            params={"url": url},
            timeout=CDP_TIMEOUT,
        )
        target_id = resp.json().get("targetId")

        if not target_id:
            return {"error": "Failed to open tab", "url": url}

        # Extract data
        js = extract_js or _default_extract_js()
        data_resp = requests.post(
            f"{CDP_BASE}/eval",
            params={"target": target_id},
            data=js,
            timeout=CDP_TIMEOUT,
        )

        try:
            return json.loads(data_resp.text)
        except json.JSONDecodeError:
            return {"raw_text": data_resp.text, "url": url}

    except requests.ConnectionError:
        return {"error": "web-access CDP not running. Enable Chrome remote debugging."}
    except requests.Timeout:
        return {"error": "CDP timeout", "url": url}
    finally:
        if target_id:
            _close_tab(target_id)


def cdp_click(target_id: str, selector: str) -> dict:
    """Click an element via CDP."""
    resp = requests.post(
        f"{CDP_BASE}/click",
        params={"target": target_id},
        data=selector,
        timeout=CDP_TIMEOUT,
    )
    return {"status": "clicked", "selector": selector}


def cdp_fill(target_id: str, selector: str, value: str) -> dict:
    """Fill an input field via CDP eval."""
    js = f'document.querySelector({json.dumps(selector)}).value = {json.dumps(value)}'
    requests.post(
        f"{CDP_BASE}/eval",
        params={"target": target_id},
        data=js,
        timeout=CDP_TIMEOUT,
    )
    return {"status": "filled", "selector": selector}


def _close_tab(target_id: str) -> None:
    try:
        requests.get(
            f"{CDP_BASE}/close",
            params={"target": target_id},
            timeout=5,
        )
    except Exception:
        pass


def _default_extract_js() -> str:
    return """JSON.stringify({
        title: document.title,
        url: location.href,
        text: document.body?.innerText?.substring(0, 3000) || '',
        meta_description: document.querySelector('meta[name=description]')?.content || ''
    })"""
