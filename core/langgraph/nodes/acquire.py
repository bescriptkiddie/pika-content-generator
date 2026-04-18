"""M1: Data Acquisition Node"""

import logging
from ..state import PipelineState
from ..tools.web_access import cdp_available, cdp_fetch_page
from ..tools.bb_browser import bb_browser_site
from ..tools.akshare_tool import fetch_a_stock
from ..tools.ccxt_tool import fetch_crypto

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
        raw_data = handler(config)
        log.info(f"[M1] {scene}: acquired {len(raw_data)} items")
        return {"raw_data": raw_data}
    except Exception as e:
        log.error(f"[M1] {scene} acquire failed: {e}")
        return {"raw_data": [], "error": str(e)}


def _acquire_xiaohongshu(config: dict) -> list[dict]:
    from ..tools.xiaohongshu import (
        fetch_hot_topics, search_notes_by_keyword,
        fetch_note_detail, fetch_explore_feed,
        fetch_platform_feed, fetch_cross_platform_trending,
        dedup_items,
    )

    mode = config.get("mode", "hot")
    results = []

    if mode == "hot":
        # Layer 1: bb-browser 热榜
        results = fetch_hot_topics()
        log.info(f"[M1] xiaohongshu hot: {len(results)} topics")

    elif mode == "search":
        # Layer 2: CDP 关键词搜索
        keywords = config.get("keywords", [])
        max_per_keyword = config.get("max_per_keyword", 10)
        for kw in keywords:
            notes = search_notes_by_keyword(kw, max_notes=max_per_keyword)
            for note in notes:
                note["search_keyword"] = kw
            results.extend(notes)
            log.info(f"[M1] xiaohongshu search '{kw}': {len(notes)} notes")

    elif mode == "explore":
        # Layer 2: CDP 发现页 feed
        results = fetch_explore_feed(max_notes=config.get("max_notes", 20))
        log.info(f"[M1] xiaohongshu explore: {len(results)} notes")

    elif mode == "trending":
        # 全站热度感知：三源融合
        all_items: list[dict] = []

        # Source 1: 小红书推荐流
        feed_items = fetch_platform_feed()
        all_items.extend(feed_items)
        log.info(f"[M1] trending/feed: {len(feed_items)} items")

        # Source 2: 关键词搜索（赛道热点）
        keywords = config.get("keywords", [])
        max_per_kw = config.get("max_per_keyword", 5)
        for kw in keywords:
            notes = search_notes_by_keyword(kw, max_notes=max_per_kw)
            for note in notes:
                note["search_keyword"] = kw
                note["source_type"] = "keyword_search"
            all_items.extend(notes)
            log.info(f"[M1] trending/search '{kw}': {len(notes)} notes")

        # Source 3: 跨平台热榜
        cross_platforms = config.get("cross_platforms", [
            "zhihu/hot", "weibo/hot", "toutiao/hot",
        ])
        cross_items = fetch_cross_platform_trending(cross_platforms)
        all_items.extend(cross_items)
        log.info(f"[M1] trending/cross-platform: {len(cross_items)} items")

        # 去重
        results = dedup_items(all_items)
        log.info(f"[M1] trending total: {len(all_items)} raw → {len(results)} deduped")

        # 可选：保存每日快照
        if config.get("save_daily_snapshot", False):
            _save_trending_snapshot(results)

    # Layer 3: 深度采集笔记详情（可选）
    if config.get("fetch_details") and cdp_available():
        top_n = config.get("detail_top_n", 5)
        for item in results[:top_n]:
            url = item.get("url", "")
            if url and "xiaohongshu.com" in url:
                detail = fetch_note_detail(url)
                if "error" not in detail:
                    item["detail"] = detail
                    log.info(f"[M1] detail fetched: {item.get('title', '')[:30]}")

    return results


def _save_trending_snapshot(items: list[dict]) -> None:
    """Save trending data to data/trending/ for historical analysis."""
    import json
    from datetime import datetime
    from pathlib import Path

    out_dir = Path(__file__).resolve().parents[3] / "data" / "trending"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"trending_{ts}.json"
    out_path.write_text(json.dumps({
        "timestamp": ts,
        "count": len(items),
        "items": items,
    }, ensure_ascii=False, indent=2))
    log.info(f"[M1] trending snapshot saved: {out_path}")


def _acquire_web(config: dict) -> list[dict]:
    results = []
    for url in config.get("urls", []):
        if config.get("need_login") and cdp_available():
            data = cdp_fetch_page(url, config.get("extract_js", ""))
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
