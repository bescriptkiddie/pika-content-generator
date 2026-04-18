"""Lightweight knowledge base — local JSON/Markdown storage.

Stores Twitter IP content as:
  data/knowledge/{name}/
    profile.json   — user profile
    tweets.json    — raw tweets (filtered)
    digest.md      — LLM-generated knowledge digest
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

KB_ROOT = Path(__file__).resolve().parents[2] / "data" / "knowledge"

# --- Tweet quality filters ---

_URL_PATTERN = re.compile(r"https?://\S+")


def filter_tweets(tweets: list[dict], *, min_likes: int = 10) -> list[dict]:
    """Filter out noise, keep substantive original content.

    Removes:
      - Pure link tweets (text is just URL(s), no real content)
      - Very short tweets (<50 chars after stripping URLs)
      - Replies (in_reply_to set) unless high engagement
      - Low engagement tweets below min_likes
    """
    kept = []
    for t in tweets:
        text = t.get("text", "").strip()
        likes = _parse_int(t.get("likes", 0))

        # Strip URLs to measure real text length
        text_no_urls = _URL_PATTERN.sub("", text).strip()

        # Skip pure link posts
        if len(text_no_urls) < 30:
            log.debug(f"[filter] skip short/link-only: {text[:60]}")
            continue

        # Skip low-engagement replies
        if t.get("in_reply_to") and likes < 100:
            log.debug(f"[filter] skip low-engagement reply: {text[:60]}")
            continue

        # Skip very low engagement
        if likes < min_likes:
            log.debug(f"[filter] skip low engagement ({likes}): {text[:60]}")
            continue

        kept.append(t)

    log.info(f"[filter] {len(tweets)} → {len(kept)} tweets after filtering")
    return kept


def _parse_int(val) -> int:
    """Safely parse engagement numbers."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.replace(",", "").replace("+", "").replace("万", "0000")
        return int(val) if val.isdigit() else 0
    return 0


def _kb_dir(name: str) -> Path:
    d = KB_ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_profile(name: str, profile: dict) -> Path:
    """Save a user profile."""
    path = _kb_dir(name) / "profile.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    log.info(f"[kb] saved profile: {path}")
    return path


def save_tweets(name: str, tweets: list[dict]) -> Path:
    """Save raw tweets."""
    path = _kb_dir(name) / "tweets.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "name": name,
            "count": len(tweets),
            "updated_at": datetime.now().isoformat(),
            "tweets": tweets,
        }, f, ensure_ascii=False, indent=2)
    log.info(f"[kb] saved {len(tweets)} tweets: {path}")
    return path


def save_digest(name: str, digest_md: str) -> Path:
    """Save LLM-generated knowledge digest."""
    path = _kb_dir(name) / "digest.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(digest_md)
    log.info(f"[kb] saved digest: {path}")
    return path


def load_tweets(name: str) -> list[dict]:
    """Load saved tweets for a user."""
    path = _kb_dir(name) / "tweets.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tweets", [])


def load_digest(name: str) -> str:
    """Load knowledge digest for a user."""
    path = _kb_dir(name) / "digest.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_knowledge(names: list[str]) -> str:
    """Load and combine digests for multiple users.

    Returns a combined markdown string for LLM context injection.
    """
    parts = []
    for name in names:
        digest = load_digest(name)
        if digest:
            parts.append(f"### {name} 的核心思想\n\n{digest}")
        else:
            log.warning(f"[kb] no digest for '{name}', run ingest first")

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)


def list_knowledge_bases() -> list[dict]:
    """List all available knowledge bases."""
    if not KB_ROOT.exists():
        return []

    result = []
    for d in sorted(KB_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        has_tweets = (d / "tweets.json").exists()
        has_digest = (d / "digest.json").exists() or (d / "digest.md").exists()
        tweet_count = 0
        if has_tweets:
            with open(d / "tweets.json", encoding="utf-8") as f:
                tweet_count = json.load(f).get("count", 0)

        result.append({
            "name": d.name,
            "has_tweets": has_tweets,
            "has_digest": has_digest,
            "tweet_count": tweet_count,
        })
    return result


def generate_digest(name: str, max_tweets: int = 80) -> str:
    """Use LLM to generate a knowledge digest from saved tweets.

    Reads tweets.json, extracts best content, sends to LLM for summarization.
    """
    from core.langgraph.tools.llm import llm_chat

    tweets = load_tweets(name)
    if not tweets:
        raise ValueError(f"No tweets found for '{name}'. Run ingest first.")

    # Sort by engagement, take top tweets
    for t in tweets:
        t["_engagement"] = _parse_int(t.get("likes", 0)) + _parse_int(t.get("retweets", 0)) * 3

    sorted_tweets = sorted(tweets, key=lambda t: t["_engagement"], reverse=True)
    top = sorted_tweets[:max_tweets]

    # Build content for LLM — skip link-only even in digest phase
    tweet_texts = []
    for t in top:
        text = t.get("text", "").strip()
        text_no_urls = _URL_PATTERN.sub("", text).strip()
        if text_no_urls and len(text_no_urls) > 20:
            engagement = f"[{t.get('likes', 0)} likes]"
            tweet_texts.append(f"{engagement} {text}")

    if not tweet_texts:
        return f"# {name}\n\n暂无有效内容"

    content_block = "\n\n".join(tweet_texts[:60])

    prompt = f"""你是一位擅长提炼思想精华的内容分析师。

以下是 Twitter/X 上 @{name} 的高互动推文内容（按互动量排序）：

{content_block}

请从这些推文中提炼出这位创作者的核心思想体系，输出结构化的知识摘要：

## 要求：
1. **核心理念**：3-5 个这位创作者最核心的思想观点
2. **方法论**：他反复提到的具体方法、框架、工具
3. **金句集锦**：10-15 条最有传播力的原始金句（保留英文原文）
4. **适用主题**：这些思想可以延展到哪些内容方向（如女性成长、职场发展、个人品牌等）
5. **内容风格**：他的表达风格特点（句式、修辞、节奏）

用 Markdown 格式输出。"""

    digest = llm_chat(prompt, max_tokens=8000, temperature=0.5)
    save_digest(name, digest)
    log.info(f"[kb] generated digest for '{name}': {len(digest)} chars")
    return digest


def ingest_twitter_user(
    screen_name: str,
    *,
    kb_name: str | None = None,
    max_tweets: int = 200,
    min_likes: int = 10,
) -> dict:
    """Full ingestion pipeline: fetch → filter → save → generate digest.

    Args:
        screen_name: Twitter handle without @ (e.g. "thedankoe")
        kb_name: Knowledge base name (e.g. "dan_koe"). Defaults to screen_name.
        max_tweets: Max tweets to fetch before filtering
        min_likes: Minimum likes to keep a tweet

    Returns:
        Summary dict with counts
    """
    from core.langgraph.tools.twitter import fetch_user_profile, fetch_all_tweets

    name = kb_name or screen_name
    log.info(f"[kb] ingesting @{screen_name} → kb:{name}")

    # Fetch profile
    profile = fetch_user_profile(screen_name)
    if "error" not in profile:
        save_profile(name, profile)

    # Fetch tweets
    raw_tweets = fetch_all_tweets(screen_name, max_tweets=max_tweets)
    log.info(f"[kb] fetched {len(raw_tweets)} raw tweets")

    # Filter
    tweets = filter_tweets(raw_tweets, min_likes=min_likes)
    save_tweets(name, tweets)

    # Generate digest
    digest = generate_digest(name)

    return {
        "name": name,
        "screen_name": screen_name,
        "profile": profile.get("name", screen_name),
        "tweets_raw": len(raw_tweets),
        "tweets_kept": len(tweets),
        "digest_length": len(digest),
    }
