"""Xiaohongshu (小红书) data extraction via bb-browser + web-access CDP"""

import json
import time
from .bb_browser import bb_browser_site
from .web_access import (
    cdp_available, cdp_open_tab, cdp_eval_json,
    cdp_scroll, cdp_close_tab,
)

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
