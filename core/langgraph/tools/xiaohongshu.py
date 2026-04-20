"""Xiaohongshu (小红书) data extraction via bb-browser + portable browser backend"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .bb_browser import bb_browser_provider_status, bb_browser_site
from .web_access import (
    browser_available,
    browser_open_tab,
    browser_eval_json,
    browser_scroll,
    browser_close_tab,
)

log = logging.getLogger(__name__)

BROWSER_PROVIDER_LABEL = "browser"
BROWSER_SEARCH_SOURCE = "browser_search"
BROWSER_EXPLORE_SOURCE = "browser_explore"

XHS_EXPLORE_URL = "https://www.xiaohongshu.com/explore"
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"
def _dailyhot_api_base(config: dict | None = None) -> str:
    if config:
        value = str(config.get("dailyhot_api_base", "")).strip()
        if value:
            return value.rstrip("/")
    value = os.getenv("DAILYHOT_API_BASE", "http://localhost:6688").strip()
    return value.rstrip("/") or "http://localhost:6688"


def fetch_hot_topics() -> list[dict]:
    raw = bb_browser_site("xiaohongshu/hot")
    topics = []
    for item in raw:
        if "error" in item:
            continue
        topics.append({
            "title": item.get("title", item.get("text", "")),
            "url": item.get("url", ""),
            "rank": item.get("rank", 0),
            "heat": item.get("heat", item.get("score", "")),
            "source": "bb-browser",
            "source_platform": "xiaohongshu",
            "source_type": "hot_topic",
        })
    return topics


def search_notes_by_keyword(keyword: str, max_notes: int = 10, config: dict | None = None) -> list[dict]:
    if not browser_available(config):
        return []

    url = XHS_SEARCH_URL.format(keyword=keyword)
    target_id = browser_open_tab(url, wait_seconds=3.0, config=config)
    if not target_id:
        return []

    try:
        browser_scroll(target_id, 2000, config=config)
        time.sleep(1.5)
        notes = browser_eval_json(target_id, _search_result_extract_js(max_notes), config=config)
        if not isinstance(notes, list):
            return []
        return [item for item in notes if _is_valid_item(item)]
    finally:
        browser_close_tab(target_id, config=config)


def search_notes_by_keyword_via_bb(keyword: str, max_notes: int = 10) -> list[dict]:
    raw = bb_browser_site(f"xiaohongshu/search {keyword}")
    results = []
    for item in raw:
        if item.get("error"):
            continue
        title = item.get("title", item.get("text", ""))
        if not title:
            continue
        results.append({
            "title": title,
            "author": item.get("author", ""),
            "likes": item.get("likes", item.get("heat", "0")),
            "url": item.get("url", ""),
            "source": "bb-browser",
            "source_platform": "xiaohongshu",
            "source_type": "keyword_search",
        })
        if len(results) >= max_notes:
            break
    return results


def bb_search_provider_status(keyword: str) -> dict:
    return bb_browser_provider_status(f"xiaohongshu/search {keyword}")


def fetch_note_detail(note_url: str, config: dict | None = None) -> dict:
    if not browser_available(config):
        return {"error": "browser provider unavailable", "error_code": "unavailable"}

    target_id = browser_open_tab(note_url, wait_seconds=3.0, config=config)
    if not target_id:
        return {"error": f"Failed to open: {note_url}", "error_code": "unavailable"}

    try:
        browser_scroll(target_id, 1500, config=config)
        time.sleep(1.0)
        detail = browser_eval_json(target_id, _note_detail_extract_js(), config=config)
        if detail:
            detail["source_url"] = note_url
            return detail
        return {"error": "Failed to extract note detail", "url": note_url, "error_code": "parse_error"}
    finally:
        browser_close_tab(target_id, config=config)


def fetch_explore_feed(max_notes: int = 20, config: dict | None = None) -> list[dict]:
    if not browser_available(config):
        return []

    target_id = browser_open_tab(XHS_EXPLORE_URL, wait_seconds=3.0, config=config)
    if not target_id:
        return []

    try:
        for _ in range(3):
            browser_scroll(target_id, 2000, config=config)
            time.sleep(1.5)

        notes = browser_eval_json(target_id, _explore_feed_extract_js(max_notes), config=config)
        if not isinstance(notes, list):
            return []
        return [item for item in notes if _is_valid_item(item)]
    finally:
        browser_close_tab(target_id, config=config)


def _search_result_extract_js(max_notes: int) -> str:
    return f"""
    (() => {{
        const cards = document.querySelectorAll('[class*="note-item"], .search-result-card, section.note-item');
        const results = [];
        const seen = new Set();
        cards.forEach(card => {{
            if (results.length >= {max_notes}) return;
            const titleEl = card.querySelector('[class*="title"], .note-title, a.title');
            const authorEl = card.querySelector('[class*="author"], .author-name, .name');
            const likesEl = card.querySelector('[class*="like"], .like-count, .count');
            const linkEl = card.querySelector('a[href*="/explore/"], a[href*="/discovery/item/"], a[href*="/search_result/"]');
            const title = titleEl?.textContent?.trim() || '';
            if (!title || seen.has(title)) return;
            seen.add(title);
            const href = linkEl?.href || card.querySelector('a')?.href || '';
            results.push({{
                title: title,
                author: authorEl?.textContent?.trim() || '',
                likes: likesEl?.textContent?.trim() || '0',
                url: href,
                source: {json.dumps(BROWSER_SEARCH_SOURCE)},
            }});
        }});
        return JSON.stringify(results);
    }})()
    """


def _note_detail_extract_js() -> str:
    return """
    (() => {
        const title = document.querySelector('#detail-title, .title, [class*="title"]')?.textContent?.trim() || '';
        const content = document.querySelector('#detail-desc, .desc, .content, [class*="content"]')?.textContent?.trim() || '';
        const author = document.querySelector('.username, .author-name, [class*="author"] .name')?.textContent?.trim() || '';
        const likes = document.querySelector('[class*="like"] .count, .like-count')?.textContent?.trim() || '0';
        const collects = document.querySelector('[class*="collect"] .count, .collect-count')?.textContent?.trim() || '0';
        const comments = document.querySelector('[class*="chat"] .count, .comment-count')?.textContent?.trim() || '0';

        const tags = [...document.querySelectorAll('#detail-tags a, .tag, [class*="tag"] a')]
            .map(t => t.textContent?.trim())
            .filter(t => t && t.startsWith('#'))
            .slice(0, 10);

        const images = [...document.querySelectorAll('.carousel img, .swiper-slide img, [class*="slide"] img')]
            .map(img => img.src || img.dataset?.src || '')
            .filter(s => s && !s.includes('avatar'))
            .slice(0, 9);

        return JSON.stringify({
            title, content, author, likes, collects, comments,
            tags, images, image_count: images.length,
        });
    })()
    """


def _explore_feed_extract_js(max_notes: int) -> str:
    return f"""
    (() => {{
        const cards = document.querySelectorAll('.note-item, [class*="note-item"], section[class*="feed"]');
        const results = [];
        const seen = new Set();
        cards.forEach(card => {{
            if (results.length >= {max_notes}) return;
            const titleEl = card.querySelector('[class*="title"], .note-title');
            const authorEl = card.querySelector('[class*="author"], .author-name');
            const likesEl = card.querySelector('[class*="like"], .like-count');
            const linkEl = card.querySelector('a[href]');
            const title = titleEl?.textContent?.trim() || '';
            if (!title || seen.has(title)) return;
            seen.add(title);
            results.push({{
                title: title,
                author: authorEl?.textContent?.trim() || '',
                likes: likesEl?.textContent?.trim() || '0',
                url: linkEl?.href || '',
                source: {json.dumps(BROWSER_EXPLORE_SOURCE)},
            }});
        }});
        return JSON.stringify(results);
    }})()
    """


def fetch_platform_feed() -> list[dict]:
    raw = bb_browser_site("xiaohongshu/feed")

    items = []
    if isinstance(raw, dict):
        raw = raw.get("notes", raw.get("items", [raw]))
    if not isinstance(raw, list):
        raw = []

    for item in raw:
        if isinstance(item, dict) and "error" not in item:
            items.append({
                "title": item.get("title", ""),
                "likes": item.get("likes", "0"),
                "url": item.get("url", ""),
                "author": item.get("author", ""),
                "source": "xhs_feed",
                "source_platform": "xiaohongshu",
            })

    log.info(f"[xhs] platform feed: {len(items)} items")
    return items


def fetch_cross_platform_trending(platforms: list[str] | None = None, config: dict | None = None) -> list[dict]:
    if platforms is None:
        platforms = ["zhihu", "toutiao", "douyin", "bilibili", "36kr"]

    all_items: list[dict] = []

    for platform in platforms:
        try:
            items = _fetch_dailyhot(platform, config=config)
            all_items.extend(items)
            log.info(f"[trending] {platform}: {len(items)} items")
        except Exception as e:
            log.warning(f"[trending] {platform} failed: {e}")

    return all_items


def _fetch_dailyhot(platform: str, config: dict | None = None) -> list[dict]:
    import subprocess

    url = f"{_dailyhot_api_base(config)}/{platform}"
    result = subprocess.run(
        ["curl", "-sf", "--max-time", "30", url],
        capture_output=True, text=True, timeout=35,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return []

    data = json.loads(result.stdout)
    if data.get("code") != 200:
        return []

    items = []
    for item in data.get("data", []):
        title = item.get("title", "")
        if not title:
            continue
        items.append({
            "title": title,
            "heat": str(item.get("hot", "")),
            "url": item.get("url", item.get("mobileUrl", "")),
            "author": item.get("author", ""),
            "source": "cross_platform",
            "source_platform": platform,
        })
    return items


_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _normalize_title(title: str) -> str:
    t = _EMOJI_RE.sub("", title)
    t = _PUNCT_RE.sub("", t)
    return t.lower().strip()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def dedup_items(items: list[dict], *, similarity_threshold: float = 0.7) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    result: list[dict] = []

    valid_items = [item for item in items if _is_valid_item(item)]
    for item in valid_items:
        url = _normalize_url(item.get("url", ""))
        if url and url in seen_urls:
            continue

        title = _normalize_title(item.get("title", ""))
        if not title:
            continue

        is_dup = False
        for existing in seen_titles:
            if SequenceMatcher(None, title, existing).ratio() > similarity_threshold:
                is_dup = True
                break

        if is_dup:
            continue

        if url:
            seen_urls.add(url)
        seen_titles.append(title)
        result.append(item)

    log.info(f"[xhs] dedup: {len(items)} → {len(result)}")
    return result


def _is_valid_item(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("error"):
        return False
    title = str(item.get("title", "")).strip()
    return bool(title)
