#!/usr/bin/env python3
"""Ingest Twitter/X users into local knowledge base.

Usage:
    python scripts/ingest_twitter.py --users dan_koe naval
    python scripts/ingest_twitter.py --users dan_koe --max-tweets 200
    python scripts/ingest_twitter.py --list
"""

import argparse
import json
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge.kb_store import ingest_twitter_user, list_knowledge_bases


def main():
    parser = argparse.ArgumentParser(description="Ingest Twitter users into knowledge base")
    parser.add_argument("--users", nargs="+", help="Twitter handles to ingest (without @)")
    parser.add_argument("--name", help="Knowledge base name (default: same as handle)")
    parser.add_argument("--max-tweets", type=int, default=200, help="Max tweets to fetch (default: 200)")
    parser.add_argument("--min-likes", type=int, default=10, help="Min likes to keep (default: 10)")
    parser.add_argument("--list", action="store_true", help="List existing knowledge bases")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    if args.list:
        kbs = list_knowledge_bases()
        if not kbs:
            print("No knowledge bases found. Run with --users to create one.")
            return
        print(f"\n{'Name':<20} {'Tweets':<10} {'Digest':<10}")
        print("-" * 40)
        for kb in kbs:
            print(f"{kb['name']:<20} {kb['tweet_count']:<10} {'✓' if kb['has_digest'] else '✗':<10}")
        return

    if not args.users:
        parser.print_help()
        return

    # If --name is given with a single user, use it as kb_name
    kb_name = args.name if (args.name and len(args.users) == 1) else None

    for user in args.users:
        name = kb_name or user
        print(f"\n{'='*50}")
        print(f"Ingesting @{user} → kb:{name}")
        print(f"{'='*50}")

        try:
            result = ingest_twitter_user(
                user,
                kb_name=kb_name,
                max_tweets=args.max_tweets,
                min_likes=args.min_likes,
            )
            print(f"\n✓ @{user} → kb:{result['name']}")
            print(f"  Profile: {result.get('profile', 'N/A')}")
            print(f"  Raw tweets: {result['tweets_raw']}")
            print(f"  After filter: {result['tweets_kept']}")
            print(f"  Digest: {result['digest_length']} chars")
        except Exception as e:
            print(f"\n✗ @{user} failed: {e}")
            logging.exception(f"Failed to ingest @{user}")

    print(f"\n{'='*50}")
    print("Done. Knowledge bases:")
    for kb in list_knowledge_bases():
        print(f"  {kb['name']}: {kb['tweet_count']} tweets, digest: {'✓' if kb['has_digest'] else '✗'}")


if __name__ == "__main__":
    main()
