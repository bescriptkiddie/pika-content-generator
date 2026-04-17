"""LLM client — unified interface for AI calls"""

import os
import json
import logging

log = logging.getLogger(__name__)

# Lazy-loaded client
_client = None


def get_llm_client():
    global _client
    if _client is None:
        try:
            from openai import OpenAI
            _client = OpenAI(
                api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
                base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            )
        except ImportError:
            raise ImportError("openai package required. Run: pip install openai")
    return _client


def llm_chat(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> str:
    """Send a chat completion request and return the response text."""
    model = model or os.getenv("LLM_MODEL", "deepseek-chat")
    client = get_llm_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return resp.choices[0].message.content.strip()


def llm_chat_json(
    prompt: str,
    system: str = "",
    model: str = "",
    temperature: float = 0.3,
) -> dict | list | None:
    """Send a chat request expecting JSON response."""
    if "JSON" not in prompt and "json" not in prompt:
        prompt += "\n\n请以JSON格式返回结果。"

    raw = llm_chat(prompt, system=system, model=model, temperature=temperature)

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning(f"LLM returned non-JSON: {text[:200]}")
        return None
