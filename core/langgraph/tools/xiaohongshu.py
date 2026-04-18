"""Xiaohongshu (小红书) data extraction via bb-browser + web-access CDP"""

import json
import logging
import re
import time
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .bb_browser import bb_browser_site
from .web_access import (
    cdp_available, cdp_open_tab, cdp_eval_json,
    cdp_scroll, cdp_close_tab,
)

log = logging.getLogger(__name__)

XHS_EXPLORE_URL = "https://www.xiaohongshu.com/explore"
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"


def fetch_hot_topics() -> list[dict]:
    """Fetch xiaohongshu hot topics via bb-browser site command."""
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
        })
    return topics


def search_notes_by_keyword(keyword: str, max_notes: int = 10) -> list[dict]:
    """Search xiaohongshu notes by keyword via CDP (needs login state)."""
    if not cdp_available():
        return [{"error": "CDP not running, cannot search xiaohongshu"}]

    url = XHS_SEARCH_URL.format(keyword=keyword)
    target_id = cdp_open_tab(url, wait_seconds=3.0)
    if not target_id:
        return [{"error": f"Failed to open search page for: {keyword}"}]

    try:
        # Scroll to load more results
        cdp_scroll(target_id, 2000)
        time.sleep(1.5)

        # Extract note cards from search results
        notes = cdp_eval_json(target_id, _search_result_extract_js(max_notes))
        return notes or []
    finally:
        cdp_close_tab(target_id)


def fetch_note_detail(note_url: str) -> dict:
    """Fetch full detail of a single xiaohongshu note via CDP."""
    if not cdp_available():
        return {"error": "CDP not running"}

    target_id = cdp_open_tab(note_url, wait_seconds=3.0)
    if not target_id:
        return {"error": f"Failed to open: {note_url}"}

    try:
        cdp_scroll(target_id, 1500)
        time.sleep(1.0)

        detail = cdp_eval_json(target_id, _note_detail_extract_js())
        if detail:
            detail["source_url"] = note_url
            return detail
        return {"error": "Failed to extract note detail", "url": note_url}
    finally:
        cdp_close_tab(target_id)


def fetch_explore_feed(max_notes: int = 20) -> list[dict]:
    """Fetch explore/discovery feed from xiaohongshu via CDP."""
    if not cdp_available():
        return [{"error": "CDP not running"}]

    target_id = cdp_open_tab(XHS_EXPLORE_URL, wait_seconds=3.0)
    if not target_id:
        return [{"error": "Failed to open explore page"}]

    try:
        # Scroll to load more content
        for _ in range(3):
            cdp_scroll(target_id, 2000)
            time.sleep(1.5)

        notes = cdp_eval_json(target_id, _explore_feed_extract_js(max_notes))
        return notes or []
    finally:
        cdp_close_tab(target_id)


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
                source: 'cdp_search',
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
                source: 'cdp_explore',
            }});
        }});
        return JSON.stringify(results);
    }})()
    """


# --- Trending awareness functions ---

def fetch_platform_feed() -> list[dict]:
    """Fetch xiaohongshu personalized feed via bb-browser.

    Returns ~35 items from the home recommendation feed with likes data.
    """
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


# Platform-specific field mappings for cross-platform trending
_PLATFORM_FIELD_MAP: dict[str, dict[str, list[str]]] = {
    "zhihu": {
        "title": ["title", "name", "question"],
        "heat": ["heat", "hot", "score", "follower_count"],
        "url": ["url", "link"],
        "items_key": ["data", "items", "questions"],
    },
    "weibo": {
        "title": ["title", "name", "word", "note"],
        "heat": ["heat", "hot", "num", "score", "raw_hot"],
        "url": ["url", "link", "scheme"],
        "items_key": ["data", "items", "trends", "realtime"],
    },
    "toutiao": {
        "title": ["title", "Title", "word", "query"],
        "heat": ["heat", "hot", "HotValue", "score"],
        "url": ["url", "Url", "link"],
        "items_key": ["data", "items"],
    },
}


def _extract_field(item: dict, candidates: list[str], default: str = "") -> str:
    """Try multiple field names to extract a value."""
    for key in candidates:
        val = item.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def _extract_items(raw, items_keys: list[str]) -> list[dict]:
    """Extract item list from raw response, trying multiple key paths."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in items_keys:
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        # Might be a flat list at top level
        return [raw] if "title" in raw or "name" in raw else []
    return []


def fetch_cross_platform_trending(
    platforms: list[str] | None = None,
) -> list[dict]:
    """Fetch hot/trending lists from cross-platform sources.

    Tries bb-browser site commands first, falls back to direct page scraping
    if site adapter times out.

    Args:
        platforms: List of bb-browser site commands, e.g. ["zhihu/hot", "weibo/hot"].
                   Defaults to zhihu + weibo + toutiao.

    Returns:
        Combined list of trending items, each tagged with source_platform.
    """
    if platforms is None:
        platforms = ["zhihu/hot", "weibo/hot", "toutiao/hot"]

    all_items: list[dict] = []

    for cmd in platforms:
        platform_name = cmd.split("/")[0]
        field_map = _PLATFORM_FIELD_MAP.get(platform_name, {
            "title": ["title", "name"],
            "heat": ["heat", "hot", "score"],
            "url": ["url", "link"],
            "items_key": ["data", "items"],
        })

        items: list[dict] = []
        try:
            raw = bb_browser_site(cmd, timeout=90)
            raw_items = _extract_items(raw, field_map["items_key"])

            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                title = _extract_field(item, field_map["title"])
                if not title:
                    continue
                items.append({
                    "title": title,
                    "heat": _extract_field(item, field_map["heat"], "0"),
                    "url": _extract_field(item, field_map["url"]),
                    "author": "",
                    "source": "cross_platform",
                    "source_platform": platform_name,
                })

        except Exception as e:
            log.warning(f"[xhs] site {cmd} failed: {e}")

        # Fallback: direct page scraping if site adapter returned nothing
        if not items:
            log.info(f"[xhs] site {cmd} returned 0, trying direct scrape")
            fallback_fn = _DIRECT_SCRAPERS.get(platform_name)
            if fallback_fn:
                try:
                    items = fallback_fn()
                except Exception as e:
                    log.warning(f"[xhs] direct scrape {platform_name} failed: {e}")

        all_items.extend(items)
        log.info(f"[xhs] cross-platform {platform_name}: {len(items)} items")

    return all_items


# --- Direct page scrapers (fallback when site adapters timeout) ---

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _fetch_zhihu_hot_api() -> list[dict]:
    """Fetch zhihu hot list via public API."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50",
            headers={**_BROWSER_HEADERS, "Referer": "https://www.zhihu.com/hot"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return [
            {
                "title": item.get("target", {}).get("title", ""),
                "heat": str(item.get("detail_text", "")),
                "url": item.get("target", {}).get("url", "").replace("api.zhihu.com/questions", "www.zhihu.com/question"),
                "author": "",
                "source": "cross_platform",
                "source_platform": "zhihu",
            }
            for item in data.get("data", [])
            if item.get("target", {}).get("title")
        ]
    except Exception as e:
        log.warning(f"[xhs] zhihu API failed: {e}")
        return []


def _fetch_weibo_hot_api() -> list[dict]:
    """Fetch weibo hot search via public API."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://weibo.com/ajax/side/hotSearch",
            headers={**_BROWSER_HEADERS, "Referer": "https://weibo.com/"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return [
            {
                "title": item.get("word", item.get("note", "")),
                "heat": str(item.get("raw_hot", item.get("num", ""))),
                "url": f"https://s.weibo.com/weibo?q=%23{item.get('word', '')}%23",
                "author": "",
                "source": "cross_platform",
                "source_platform": "weibo",
            }
            for item in data.get("data", {}).get("realtime", [])
            if item.get("word")
        ]
    except Exception as e:
        log.warning(f"[xhs] weibo API failed: {e}")
        return []


def _fetch_toutiao_hot_api() -> list[dict]:
    """Fetch toutiao hot list via public API."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return [
            {
                "title": item.get("Title", item.get("title", "")),
                "heat": str(item.get("HotValue", item.get("hot_value", ""))),
                "url": item.get("Url", item.get("url", "")),
                "author": "",
                "source": "cross_platform",
                "source_platform": "toutiao",
            }
            for item in data.get("data", [])
            if item.get("Title") or item.get("title")
        ]
    except Exception as e:
        log.warning(f"[xhs] toutiao API failed: {e}")
        return []


_DIRECT_SCRAPERS: dict[str, callable] = {
    "zhihu": _fetch_zhihu_hot_api,
    "weibo": _fetch_weibo_hot_api,
    "toutiao": _fetch_toutiao_hot_api,
}


# --- Deduplication ---

_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _normalize_title(title: str) -> str:
    """Normalize title for similarity comparison."""
    t = _EMOJI_RE.sub("", title)
    t = _PUNCT_RE.sub("", t)
    return t.lower().strip()


def _normalize_url(url: str) -> str:
    """Normalize URL for dedup (strip query params and trailing slash)."""
    if not url:
        return ""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def dedup_items(items: list[dict], *, similarity_threshold: float = 0.7) -> list[dict]:
    """Deduplicate items by URL identity and title similarity.

    Earlier items in the list have priority (first-seen wins).
    When a duplicate is found, keep the one with more engagement data.
    """
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    result: list[dict] = []

    for item in items:
        # URL dedup
        url = _normalize_url(item.get("url", ""))
        if url and url in seen_urls:
            continue

        # Title similarity dedup
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
