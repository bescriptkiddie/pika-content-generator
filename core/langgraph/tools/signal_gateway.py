from __future__ import annotations

from typing import Any

from .signal_validator import build_failure_state, build_signal_summary, filter_usable_items, is_usable_signal
from .web_access import browser_status
from .xhs_cli_provider import fetch_feed as xhs_cli_fetch_feed
from .xhs_cli_provider import search_notes as xhs_cli_search_notes
from .xhs_cli_provider import xhs_cli_status
from .xiaohongshu import (
    bb_search_provider_status,
    dedup_items,
    fetch_cross_platform_trending,
    fetch_explore_feed,
    fetch_hot_topics,
    fetch_platform_feed,
    search_notes_by_keyword,
    search_notes_by_keyword_via_bb,
)

DEFAULT_PROVIDER_ORDER = {
    "hot": ["bb_hot"],
    "feed": ["xhs_cli_feed", "bb_feed", "browser_feed"],
    "search": ["xhs_cli_search", "bb_search", "browser_search"],
    "cross_platform": ["hosted_cross_platform"],
}

_PROVIDER_ALIASES = {
    "browser_search": "browser_search",
    "cdp_search": "browser_search",
    "browser_feed": "browser_feed",
    "cdp_feed": "browser_feed",
    "browser_explore": "browser_feed",
    "cdp_explore": "browser_feed",
}


def acquire_xiaohongshu_signals(config: dict[str, Any]) -> dict[str, Any]:
    mode = config.get("mode", "hot")
    provider_order = config.get("provider_order", DEFAULT_PROVIDER_ORDER)
    provider_trace: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    if mode == "hot":
        items = fetch_hot_topics()
        provider_trace.append(_trace_entry("bb-browser:hot", items, _provider_status_from_items(items, provider="bb-browser", empty_action="none")))
        candidates = filter_usable_items(items)

    elif mode == "explore":
        items = fetch_explore_feed(max_notes=config.get("max_notes", 20), config=config)
        provider_trace.append(_trace_entry("browser:explore", items, _browser_provider_status(items, provider="browser", config=config)))
        candidates = filter_usable_items(items)

    elif mode == "search":
        candidates = _search_keyword_candidates(config, provider_trace, provider_order)

    elif mode == "trending":
        feed_items = _resolve_feed_with_providers(config, provider_trace, provider_order)
        candidates.extend(feed_items)

        search_items = _search_keyword_candidates(config, provider_trace, provider_order)
        candidates.extend(search_items)

        cross_platforms = config.get("cross_platforms", ["zhihu", "toutiao", "douyin", "bilibili", "36kr"])
        cross_items = fetch_cross_platform_trending(cross_platforms, config=config)
        provider_trace.append(
            _trace_entry(
                "hosted:cross_platform",
                cross_items,
                _provider_status_from_items(cross_items, provider="hosted-api", empty_action="retry_later"),
            )
        )
        candidates.extend(filter_usable_items(cross_items))

    deduped = dedup_items(candidates)
    usable = is_usable_signal(deduped)
    signal_summary = build_signal_summary(deduped)
    failure_state = None if usable else _collapse_failure_state(provider_trace)
    return {
        "items": deduped,
        "usable": usable,
        "provider_trace": provider_trace,
        "signal_summary": signal_summary,
        "failure_state": failure_state,
        "action_required": failure_state.get("action_required", "none") if failure_state else "none",
        "degraded": not usable,
    }


def _resolve_feed_with_providers(
    config: dict[str, Any],
    provider_trace: list[dict[str, Any]],
    provider_order: dict[str, list[str]],
) -> list[dict[str, Any]]:
    providers = provider_order.get("feed", DEFAULT_PROVIDER_ORDER["feed"])
    for raw_provider in providers:
        provider = _normalize_provider(raw_provider)
        if provider == "xhs_cli_feed":
            items = xhs_cli_fetch_feed(max_notes=config.get("max_notes", 20))
            status = _xhs_cli_provider_status(items)
            provider_trace.append(_trace_entry("xhs-cli:feed", items, status))
            if status["status"] == "success":
                return filter_usable_items(items)
        elif provider == "bb_feed":
            items = fetch_platform_feed()
            status = _provider_status_from_items(items, provider="bb-browser", empty_action="none")
            provider_trace.append(_trace_entry("bb-browser:feed", items, status))
            if status["status"] == "success":
                return filter_usable_items(items)
        elif provider == "browser_feed":
            items = fetch_explore_feed(max_notes=config.get("max_notes", 20), config=config)
            status = _browser_provider_status(items, provider="browser", config=config)
            provider_trace.append(_trace_entry(_feed_trace_name(raw_provider), items, status))
            if status["status"] == "success":
                return filter_usable_items(items)
    return []


def _search_keyword_candidates(
    config: dict[str, Any],
    provider_trace: list[dict[str, Any]],
    provider_order: dict[str, list[str]],
) -> list[dict[str, Any]]:
    keywords = config.get("keywords", [])
    max_per_keyword = config.get("max_per_keyword", 10)
    providers = provider_order.get("search", DEFAULT_PROVIDER_ORDER["search"])
    all_items: list[dict[str, Any]] = []
    for keyword in keywords:
        items = _resolve_search_with_providers(keyword, max_per_keyword, providers, provider_trace, config)
        keyword_items = [
            {
                **item,
                "search_keyword": keyword,
                "source_type": item.get("source_type", "keyword_search"),
            }
            for item in items
        ]
        all_items.extend(filter_usable_items(keyword_items))
    return all_items


def _resolve_search_with_providers(
    keyword: str,
    max_notes: int,
    providers: list[str],
    provider_trace: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    for raw_provider in providers:
        provider = _normalize_provider(raw_provider)
        if provider == "xhs_cli_search":
            items = xhs_cli_search_notes(keyword, max_notes=max_notes)
            status = _xhs_cli_provider_status(items)
            provider_trace.append(_trace_entry(f"xhs-cli:search:{keyword}", items, status))
            if status["status"] == "success":
                return items
        elif provider == "bb_search":
            items = search_notes_by_keyword_via_bb(keyword, max_notes=max_notes)
            status = bb_search_provider_status(keyword)
            provider_trace.append(_trace_entry(f"bb-browser:search:{keyword}", items, status))
            if status["status"] == "success":
                return items
        elif provider == "browser_search":
            items = search_notes_by_keyword(keyword, max_notes=max_notes, config=config)
            status = _browser_provider_status(items, provider="browser", config=config)
            provider_trace.append(_trace_entry(_search_trace_name(raw_provider, keyword), items, status))
            if status["status"] == "success":
                return items
    return []


def _provider_status_from_items(items: list[dict[str, Any]], *, provider: str, empty_action: str) -> dict[str, Any]:
    summary = build_signal_summary(items)
    if summary["usable"]:
        return {
            "status": "success",
            "reason": "",
            "retryable": False,
            "action_required": "none",
            "action_hint": "",
            "provider": provider,
        }
    return {
        "status": "empty",
        "reason": "provider returned empty result",
        "retryable": True,
        "action_required": empty_action,
        "action_hint": "",
        "provider": provider,
    }


def _xhs_cli_provider_status(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = build_signal_summary(items)
    if summary["usable"]:
        return {
            "status": "success",
            "reason": "",
            "retryable": False,
            "action_required": "none",
            "action_hint": "",
            "provider": "xhs-cli",
        }
    error_item = _first_error_item(items)
    if error_item:
        return {
            "status": str(error_item.get("error_code", "error")),
            "reason": str(error_item.get("error", "xhs-cli provider error")),
            "retryable": bool(error_item.get("retryable", False)),
            "action_required": str(error_item.get("action_required", "none")),
            "action_hint": str(error_item.get("action_hint", "")),
            "provider": "xhs-cli",
            "verification_required": bool(error_item.get("verification_required", False)),
            "verify_type": str(error_item.get("verify_type", "")),
            "verify_uuid": str(error_item.get("verify_uuid", "")),
        }
    status = xhs_cli_status()
    return {
        **status,
        "provider": "xhs-cli",
    }


def _browser_provider_status(items: list[dict[str, Any]], *, provider: str, config: dict[str, Any]) -> dict[str, Any]:
    if items:
        return {
            "status": "success",
            "reason": "",
            "retryable": False,
            "action_required": "none",
            "action_hint": "",
            "provider": provider,
        }
    status = browser_status(config)
    return {
        **status,
        "provider": provider,
    }


def _trace_entry(provider: str, items: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, Any]:
    summary = build_signal_summary(items)
    trace = {
        "provider": provider,
        "status": status["status"],
        "usable": summary["usable"],
        "count": summary["count"],
        "usable_count": summary["usable_count"],
        "retryable": status.get("retryable", False),
        "action_required": status.get("action_required", "none"),
        "action_hint": status.get("action_hint", ""),
        "reason": status.get("reason", ""),
    }
    if status.get("verification_required"):
        trace["verification_required"] = True
    if status.get("verify_type"):
        trace["verify_type"] = status["verify_type"]
    if status.get("verify_uuid"):
        trace["verify_uuid"] = status["verify_uuid"]
    return trace


def _collapse_failure_state(provider_trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    for trace in provider_trace:
        if trace["status"] in {"auth_expired", "verification_required", "timeout", "unavailable", "error"}:
            return build_failure_state(
                kind=trace["status"],
                stage="acquire",
                provider=trace["provider"],
                reason=trace.get("reason", ""),
                retryable=trace.get("retryable", False),
                action_required=trace.get("action_required", "none"),
                action_hint=trace.get("action_hint", ""),
                verification_required=bool(trace.get("verification_required", False)),
                verify_type=str(trace.get("verify_type", "")),
                verify_uuid=str(trace.get("verify_uuid", "")),
            )
    if provider_trace:
        return build_failure_state(
            kind="empty",
            stage="acquire",
            provider=provider_trace[-1]["provider"],
            reason="all providers returned empty signals",
            retryable=True,
            action_required="none",
            action_hint="",
        )
    return None


def _first_error_item(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in items:
        if isinstance(item, dict) and item.get("error_code"):
            return item
    return None


def _normalize_provider(provider: str) -> str:
    return _PROVIDER_ALIASES.get(provider, provider)


def _search_trace_name(provider: str, keyword: str) -> str:
    if provider == "cdp_search":
        return f"cdp:search:{keyword}"
    return f"browser:search:{keyword}"


def _feed_trace_name(provider: str) -> str:
    if provider in {"cdp_feed", "cdp_explore"}:
        return "cdp:feed"
    return "browser:feed"
