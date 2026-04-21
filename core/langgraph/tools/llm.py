"""LLM client — Claude-compatible Messages API"""

import os
import json
import logging
from pathlib import Path

import requests as http

log = logging.getLogger(__name__)

_config = None


def _load_dotenv():
    """Load .env file from project root."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not os.getenv(key):
            os.environ[key] = value


def _normalize_base_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return base_url
    return f"{base_url}/v1"


def _get_config() -> dict:
    global _config
    if _config is None:
        _load_dotenv()
        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://api.anthropic.com")
        if not api_key:
            raise ValueError("LLM_API_KEY not set. Copy .env.example to .env and fill in your key.")
        _config = {
            "api_key": api_key,
            "base_url": _normalize_base_url(base_url),
            "model": os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
        }
    return _config


def llm_chat(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> str:
    """Send a message via Claude-compatible Messages API and return response text."""
    cfg = _get_config()
    model = model or cfg["model"]
    url = f"{cfg['base_url']}/messages"

    headers = {
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    if temperature != 1.0:
        body["temperature"] = temperature

    resp = http.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    content = data.get("content", [])
    if content and content[0].get("type") == "text":
        return content[0]["text"].strip()

    raise ValueError(f"Unexpected LLM response: {json.dumps(data)[:300]}")


def llm_chat_json(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.3,
) -> dict | list | None:
    """Send a message expecting JSON response."""
    if "JSON" not in prompt and "json" not in prompt:
        prompt += "\n\n请以纯JSON格式返回结果，不要包含其他内容。"

    raw = llm_chat(prompt, system=system, model=model, temperature=temperature)

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning(f"LLM returned non-JSON: {text[:200]}")
        return None
