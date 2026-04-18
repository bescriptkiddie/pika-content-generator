#!/usr/bin/env python3
"""Ingest Twitter IP content via bb-browser site commands.

Usage:
    python scripts/ingest_via_bb.py --users thedankoe naval --max-tweets 200
"""

import argparse
import json
import logging
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge.kb_store import save_profile, save_tweets, save_digest, generate_digest, list_knowledge_bases

log = logging.getLogger(__name__)


def bb_site(command: str, timeout: int = 45) -> dict | list:
    """Run bb-browser site command and return parsed JSON."""
    cmd = ["bb-browser", "site"] + command.split()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"bb-browser failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_profile(screen_name: str) -> dict:
    """Fetch Twitter user profile."""
    return bb_site(f"twitter/user {screen_name}")


def fetch_tweets_paginated(screen_name: str, max_tweets: int = 200) -> list[dict]:
    """Fetch tweets with cursor pagination."""
    all_tweets = []
    cursor = None

    while len(all_tweets) < max_tweets:
        cmd = f"twitter/tweets {screen_name} --count 100"
        if cursor:
            cmd += f" --cursor {cursor}"

        data = bb_site(cmd, timeout=60)
        tweets = data.get("tweets", [])
        if not tweets:
            break

        all_tweets.extend(tweets)
        print(f"    fetched {len(all_tweets)} tweets so far...")

        cursor = data.get("next_cursor")
        if not cursor:
            break

    return all_tweets[:max_tweets]


def ingest_user(screen_name: str, kb_name: str, max_tweets: int = 200) -> dict:
    """Full ingestion: profile → tweets → digest."""

    # Step 1: Profile
    print(f"  [1/3] Fetching profile for @{screen_name}...")
    profile = fetch_profile(screen_name)
    save_profile(kb_name, profile)
    print(f"        → {profile.get('name')} ({profile.get('followers', '?')} followers)")

    # Step 2: Tweets
    print(f"  [2/3] Fetching tweets (max {max_tweets})...")
    tweets = fetch_tweets_paginated(screen_name, max_tweets)
    save_tweets(kb_name, tweets)
    print(f"        → {len(tweets)} tweets saved")

    # Step 3: Generate digest via LLM
    print(f"  [3/3] Generating knowledge digest via LLM...")
    digest = generate_digest(kb_name)
    print(f"        → {len(digest)} chars digest")

    return {
        "name": kb_name,
        "screen_name": screen_name,
        "tweets_count": len(tweets),
        "digest_length": len(digest),
    }


# Map of known IPs: kb_name → twitter handle
KNOWN_IPS = {
    "dan_koe": "thedankoe",  # @thedankoe (903K followers)
    "naval": "naval",         # @naval (3.1M followers)
}


def main():
    parser = argparse.ArgumentParser(description="Ingest Twitter IPs via bb-browser")
    parser.add_argument("--users", nargs="+", default=list(KNOWN_IPS.keys()),
                        help="KB names to ingest (default: dan_koe naval)")
    parser.add_argument("--max-tweets", type=int, default=200,
                        help="Max tweets per user (default: 200)")
    parser.add_argument("--list", action="store_true", help="List existing KBs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    if args.list:
        for kb in list_knowledge_bases():
            print(f"  {kb['name']}: {kb['tweet_count']} tweets, digest: {'✓' if kb['has_digest'] else '✗'}")
        return

    for kb_name in args.users:
        handle = KNOWN_IPS.get(kb_name, kb_name)
        print(f"\n{'='*50}")
        print(f"Ingesting @{handle} → KB '{kb_name}'")
        print(f"{'='*50}")
        try:
            result = ingest_user(handle, kb_name, max_tweets=args.max_tweets)
            print(f"\n✓ Done: {result['tweets_count']} tweets, {result['digest_length']} chars digest")
        except Exception as e:
            print(f"\n✗ Failed: {e}")
            log.exception(f"Failed @{handle}")

    print(f"\n{'='*50}")
    print("Knowledge bases:")
    for kb in list_knowledge_bases():
        print(f"  {kb['name']}: {kb['tweet_count']} tweets, digest: {'✓' if kb['has_digest'] else '✗'}")


if __name__ == "__main__":
    main()
