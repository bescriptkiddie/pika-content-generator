"""Twitter/X data acquisition via bb-browser"""

import logging
from .bb_browser import bb_browser_site

log = logging.getLogger(__name__)


def fetch_user_profile(screen_name: str) -> dict:
    """Fetch a Twitter user's profile info."""
    raw = bb_browser_site(f"twitter/user {screen_name}")
    if isinstance(raw, list) and raw and "error" not in raw[0]:
        return raw[0]
    if isinstance(raw, dict):
        return raw
    return {"error": f"Failed to fetch profile for @{screen_name}", "raw": raw}


def fetch_user_tweets(screen_name: str, count: int = 100) -> list[dict]:
    """Fetch a user's recent tweets.

    Args:
        screen_name: Twitter handle without @
        count: Number of tweets (max 100 per request)

    Returns:
        List of tweet dicts with: id, text, likes, retweets, replies, created_at, author, url
    """
    raw = bb_browser_site(f"twitter/tweets {screen_name} --count {count}")

    tweets = _extract_tweets(raw)

    # Fallback to search if tweets endpoint is rate-limited
    if not tweets and _is_error(raw, "429"):
        log.warning(f"[twitter] @{screen_name}: tweets endpoint 429, falling back to search")
        tweets = _search_fallback(screen_name, count)

    log.info(f"[twitter] @{screen_name}: fetched {len(tweets)} tweets")
    return tweets


def fetch_all_tweets(screen_name: str, max_tweets: int = 300) -> list[dict]:
    """Fetch multiple pages of tweets using cursor pagination.

    Falls back to twitter/search if twitter/tweets is rate-limited.

    Args:
        screen_name: Twitter handle without @
        max_tweets: Maximum total tweets to fetch
    """
    all_tweets = []
    cursor = None
    per_page = min(100, max_tweets)
    use_search = False

    while len(all_tweets) < max_tweets:
        if use_search:
            # Search fallback: no cursor pagination, fetch remaining in one shot
            remaining = max_tweets - len(all_tweets)
            new_tweets = _search_fallback(screen_name, min(remaining, 50))
            # Deduplicate by id
            seen_ids = {t.get("id") for t in all_tweets}
            new_tweets = [t for t in new_tweets if t.get("id") not in seen_ids]
            if new_tweets:
                all_tweets.extend(new_tweets)
                log.info(f"[twitter] @{screen_name}: {len(all_tweets)} tweets (via search fallback)")
            break

        cmd = f"twitter/tweets {screen_name} --count {per_page}"
        if cursor:
            cmd += f" --cursor {cursor}"

        raw = bb_browser_site(cmd)

        # Check for rate limit → switch to search
        if _is_error(raw, "429"):
            log.warning(f"[twitter] @{screen_name}: 429 at {len(all_tweets)} tweets, switching to search")
            use_search = True
            continue

        if isinstance(raw, dict):
            tweets = raw.get("tweets", [])
            cursor = raw.get("next_cursor")
        elif isinstance(raw, list):
            tweets = [t for t in raw if isinstance(t, dict) and "text" in t]
            cursor = None
        else:
            break

        if not tweets:
            break

        all_tweets.extend(tweets)
        log.info(f"[twitter] @{screen_name}: {len(all_tweets)} tweets so far")

        if not cursor:
            break

    return all_tweets[:max_tweets]


def _extract_tweets(raw) -> list[dict]:
    """Extract tweet list from raw bb-browser response."""
    if isinstance(raw, dict) and "tweets" in raw:
        return raw["tweets"]
    if isinstance(raw, list):
        return [t for t in raw if isinstance(t, dict) and "text" in t]
    return []


def _is_error(raw, code: str) -> bool:
    """Check if raw response contains a specific error code."""
    if isinstance(raw, list) and raw:
        err = raw[0].get("error", "") if isinstance(raw[0], dict) else ""
        return code in str(err)
    if isinstance(raw, dict):
        return code in str(raw.get("error", ""))
    return False


def _search_fallback(screen_name: str, count: int = 50) -> list[dict]:
    """Fetch tweets via twitter/search as fallback when tweets endpoint is rate-limited."""
    cmd = f'twitter/search "from:{screen_name}" --count {min(count, 50)}'
    raw = bb_browser_site(cmd)
    return _extract_tweets(raw)


def search_tweets(query: str, count: int = 50, sort: str = "top") -> list[dict]:
    """Search Twitter for tweets matching a query.

    Args:
        query: Search query string
        count: Number of results (max 50)
        sort: "top" or "latest"
    """
    cmd = f'twitter/search "{query}" --count {count} --type {sort}'
    raw = bb_browser_site(cmd)

    tweets = []
    if isinstance(raw, dict) and "tweets" in raw:
        tweets = raw["tweets"]
    elif isinstance(raw, list):
        tweets = [t for t in raw if isinstance(t, dict) and "text" in t]

    log.info(f"[twitter] search '{query}': {len(tweets)} results")
    return tweets
