"""M1: Data Acquisition Node"""

import logging
from ..state import PipelineState
from ..tools.web_access import browser_available, browser_fetch_page
from ..tools.bb_browser import bb_browser_site
from ..tools.akshare_tool import fetch_a_stock
from ..tools.ccxt_tool import fetch_crypto
from ..tools.signal_validator import build_failure_state

log = logging.getLogger(__name__)


def acquire_node(state: PipelineState) -> dict:
    scene = state["scene"]
    config = state.get("acquire_config", {})

    handlers = {
        "xiaohongshu": _acquire_xiaohongshu,
        "gallup": _acquire_web,
        "geo": _acquire_web,
        "quant_a_stock": _acquire_a_stock,
        "quant_crypto": _acquire_crypto,
    }

    handler = handlers.get(scene)
    if not handler:
        return {"raw_data": [], "error": f"Unknown scene: {scene}"}

    try:
        acquire_result = handler(config)
        if isinstance(acquire_result, list):
            raw_data = acquire_result
            provider_trace = []
            signal_summary = {"usable": bool(raw_data), "usable_count": len(raw_data)}
            failure_state = None
            action_required = "none"
            degraded = False
        else:
            raw_data = acquire_result.get("items", [])
            provider_trace = acquire_result.get("provider_trace", [])
            signal_summary = acquire_result.get("signal_summary", {"usable": bool(raw_data), "usable_count": len(raw_data)})
            failure_state = acquire_result.get("failure_state")
            action_required = acquire_result.get("action_required", "none")
            degraded = acquire_result.get("degraded", False)
        decision = state.get("decision", {})
        if scene == "xiaohongshu":
            if not signal_summary.get("usable"):
                raw_data = _fallback_seed_topics(config)
                decision = {
                    **decision,
                    "fallback_seed_used": True,
                    "fallback_reason": "external_acquire_returned_empty",
                }
                provider_trace.append({
                    "provider": "seed_fallback",
                    "status": "success",
                    "usable": True,
                    "count": len(raw_data),
                    "usable_count": len(raw_data),
                    "retryable": False,
                    "action_required": "none",
                    "action_hint": "",
                    "reason": "fallback topic seeds generated",
                })
                degraded = True
                if not failure_state:
                    failure_state = build_failure_state(
                        kind="empty",
                        stage="acquire",
                        provider="signal_gateway",
                        reason="all providers returned empty signals",
                        retryable=True,
                        action_required="none",
                        action_hint="",
                    )
            else:
                decision = {
                    **decision,
                    "fallback_seed_used": False,
                }
            decision = {
                **decision,
                "provider_trace": provider_trace,
                "signal_summary": signal_summary,
            }
        log.info(f"[M1] {scene}: acquired {len(raw_data)} items")
        if scene == "xiaohongshu":
            decision = {
                **decision,
                "input_summary": {
                    "mode": config.get("mode", "hot"),
                    "keywords": config.get("keywords", []),
                    "domain": config.get("domain", "通用"),
                    "target_audience": config.get("target_audience", "年轻人"),
                    "knowledge_sources": config.get("knowledge_sources", []),
                }
            }
        return {
            "raw_data": raw_data,
            "decision": decision,
            "failure_state": failure_state,
            "action_required": action_required,
            "degraded": degraded,
        }
    except Exception as e:
        log.error(f"[M1] {scene} acquire failed: {e}")
        return {"raw_data": [], "error": str(e)}


def _acquire_xiaohongshu(config: dict) -> dict:
    from ..tools.signal_gateway import acquire_xiaohongshu_signals
    from ..tools.xiaohongshu import fetch_note_detail

    result = acquire_xiaohongshu_signals(config)
    items = result.get("items", [])

    if config.get("fetch_details") and browser_available(config):
        top_n = config.get("detail_top_n", 5)
        for item in items[:top_n]:
            url = item.get("url", "")
            if url and "xiaohongshu.com" in url:
                detail = fetch_note_detail(url, config=config)
                if "error" not in detail:
                    item["detail"] = detail
                    log.info(f"[M1] detail fetched: {item.get('title', '')[:30]}")

    result["items"] = items
    return result


def _fallback_seed_topics(config: dict) -> list[dict]:
    keywords = config.get("keywords", []) or [config.get("domain", "AI效率")]
    seeds = []
    for index, keyword in enumerate(keywords[:5]):
        seeds.append({
            "title": f"{keyword} 的真实痛点与可执行方法",
            "author": "seed-generator",
            "likes": 0,
            "url": "",
            "source": "seed_fallback",
            "source_platform": "internal",
            "source_type": "seed_topic",
            "search_keyword": keyword,
            "seed_index": index,
        })
    return seeds


def _acquire_web(config: dict) -> list[dict]:
    results = []
    for url in config.get("urls", []):
        if config.get("need_login") and browser_available(config):
            data = browser_fetch_page(url, config.get("extract_js", ""), config=config)
        else:
            data = bb_browser_site(f"open {url}")
            data = data[0] if data else {}
        results.append({"url": url, "data": data})
    return results


def _acquire_a_stock(config: dict) -> list[dict]:
    symbols = config.get("symbols", [config.get("symbol", "000001")])
    all_data = []
    for symbol in symbols:
        data = fetch_a_stock(
            symbol=symbol,
            period=config.get("period", "daily"),
            days=config.get("days", 30),
        )
        all_data.extend(data)
    return all_data


def _acquire_crypto(config: dict) -> list[dict]:
    pairs = config.get("pairs", [config.get("pair", "BTC/USDT")])
    all_data = []
    for pair in pairs:
        data = fetch_crypto(
            pair=pair,
            exchange_id=config.get("exchange", "binance"),
            timeframe=config.get("timeframe", "1h"),
            limit=config.get("limit", 100),
        )
        all_data.extend(data)
    return all_data
