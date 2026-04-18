#!/usr/bin/env python3
"""Batch ingest multiple Twitter IPs into knowledge bases.

Usage:
    python scripts/batch_ingest_ips.py
    python scripts/batch_ingest_ips.py --dry-run
    python scripts/batch_ingest_ips.py --only alex_hormozi sahil_bloom
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge.kb_store import ingest_twitter_user, list_knowledge_bases

# IP registry: kb_name → twitter handle
IP_REGISTRY: list[dict] = [
    # Tier 1: 核心 IP
    {"kb_name": "dan_koe",       "handle": "thedankoe",      "tier": 1, "label": "一人企业/个人成长"},
    {"kb_name": "naval",         "handle": "naval",           "tier": 1, "label": "财富/幸福哲学"},
    {"kb_name": "alex_hormozi",  "handle": "AlexHormozi",     "tier": 1, "label": "商业增长/变现"},
    {"kb_name": "sahil_bloom",   "handle": "SahilBloom",      "tier": 1, "label": "人生框架/五种财富"},
    {"kb_name": "james_clear",   "handle": "JamesClear",      "tier": 1, "label": "习惯/微小改变"},
    {"kb_name": "justin_welsh",  "handle": "thejustinwelsh",  "tier": 1, "label": "一人公司/副业"},
    # Tier 2: 写作 + 哲学深度
    {"kb_name": "ryan_holiday",  "handle": "RyanHoliday",     "tier": 2, "label": "斯多葛哲学/自律"},
    {"kb_name": "nicolas_cole",  "handle": "Nicolascole77",   "tier": 2, "label": "写作变现/个人品牌"},
    {"kb_name": "dickie_bush",   "handle": "dickiebush",      "tier": 2, "label": "数字写作/网络生意"},
    {"kb_name": "mark_manson",   "handle": "Markmanson",      "tier": 2, "label": "人生哲学/反鸡汤"},
]


def main():
    parser = argparse.ArgumentParser(description="Batch ingest Twitter IPs")
    parser.add_argument("--only", nargs="+", help="Only ingest these kb_names")
    parser.add_argument("--max-tweets", type=int, default=200, help="Max tweets per IP (default: 200)")
    parser.add_argument("--min-likes", type=int, default=50, help="Min likes filter (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested")
    args = parser.parse_args()

    targets = IP_REGISTRY
    if args.only:
        targets = [ip for ip in IP_REGISTRY if ip["kb_name"] in args.only]

    if args.dry_run:
        print(f"\n{'KB Name':<18} {'Handle':<20} {'Tier':<6} {'Label'}")
        print("-" * 70)
        for ip in targets:
            print(f"{ip['kb_name']:<18} @{ip['handle']:<19} T{ip['tier']:<5} {ip['label']}")
        print(f"\nTotal: {len(targets)} IPs")
        return

    results = []
    failed = []

    for i, ip in enumerate(targets, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(targets)}] @{ip['handle']} → kb:{ip['kb_name']} ({ip['label']})")
        print(f"{'='*60}")

        try:
            result = ingest_twitter_user(
                ip["handle"],
                kb_name=ip["kb_name"],
                max_tweets=args.max_tweets,
                min_likes=args.min_likes,
            )
            results.append(result)
            print(f"\n  ✓ Raw: {result['tweets_raw']} → Filtered: {result['tweets_kept']} → Digest: {result['digest_length']} chars")
        except Exception as e:
            failed.append({"name": ip["kb_name"], "error": str(e)})
            print(f"\n  ✗ Failed: {e}")

        # Pause between requests to avoid rate limiting
        if i < len(targets):
            time.sleep(5)

    # Summary
    print(f"\n\n{'='*60}")
    print("BATCH INGEST SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'KB Name':<18} {'Raw':<8} {'Kept':<8} {'Digest':<10} {'Status'}")
    print("-" * 60)

    for r in results:
        print(f"{r['name']:<18} {r['tweets_raw']:<8} {r['tweets_kept']:<8} {r['digest_length']:<10} ✓")
    for f in failed:
        print(f"{f['name']:<18} {'—':<8} {'—':<8} {'—':<10} ✗ {f['error'][:30]}")

    print(f"\nSuccess: {len(results)} | Failed: {len(failed)} | Total: {len(targets)}")


if __name__ == "__main__":
    main()
