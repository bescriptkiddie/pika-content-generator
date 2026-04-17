"""M1: Data Acquisition Node"""

from ..state import PipelineState
from ..tools.bb_browser import bb_browser_site
from ..tools.web_access import cdp_fetch_page
from ..tools.akshare_tool import fetch_a_stock
from ..tools.ccxt_tool import fetch_crypto


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

    raw_data = handler(config)
    return {"raw_data": raw_data}


def _acquire_xiaohongshu(config: dict) -> list[dict]:
    # Layer 1: bb-browser 快速热榜
    hot_topics = bb_browser_site("xiaohongshu/hot")

    # Layer 2: web-access 深度采集（可选）
    if config.get("deep_scrape") and hot_topics:
        top_n = config.get("top_n", 5)
        for topic in hot_topics[:top_n]:
            url = topic.get("url", "")
            if url:
                detail = cdp_fetch_page(url, config.get("extract_js", ""))
                topic["detail"] = detail

    return hot_topics


def _acquire_web(config: dict) -> list[dict]:
    results = []
    for url in config.get("urls", []):
        data = bb_browser_site(f"open {url}") if not config.get("need_login") \
            else cdp_fetch_page(url, config.get("extract_js", ""))
        results.append({"url": url, "data": data})
    return results


def _acquire_a_stock(config: dict) -> list[dict]:
    return fetch_a_stock(
        symbol=config.get("symbol", "000001"),
        period=config.get("period", "daily"),
        days=config.get("days", 30),
    )


def _acquire_crypto(config: dict) -> list[dict]:
    return fetch_crypto(
        pair=config.get("pair", "BTC/USDT"),
        exchange_id=config.get("exchange", "binance"),
        timeframe=config.get("timeframe", "1h"),
        limit=config.get("limit", 100),
    )
