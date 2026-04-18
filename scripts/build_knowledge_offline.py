#!/usr/bin/env python3
"""Build knowledge base for well-known IPs using LLM knowledge (no browser needed).

Usage:
    python scripts/build_knowledge_offline.py --users dan_koe naval
"""

import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge.kb_store import save_profile, save_tweets, save_digest, generate_digest, list_knowledge_bases
from core.langgraph.tools.llm import llm_chat, llm_chat_json

log = logging.getLogger(__name__)

# Well-known IP profiles
IP_PROFILES = {
    "dan_koe": {
        "screen_name": "dan_koe",
        "name": "Dan Koe",
        "bio": "Writer, entrepreneur, and philosopher. Building The One-Person Business Model. Author of The Art of Focus.",
        "followers": "800K+",
        "known_for": "One-person business, digital economics, creativity, self-education",
    },
    "naval": {
        "screen_name": "naval",
        "name": "Naval Ravikant",
        "bio": "Angel investor, philosopher. Co-founder of AngelList. Seeking wealth, health, and happiness.",
        "followers": "2M+",
        "known_for": "Wealth creation, leverage, specific knowledge, happiness philosophy",
    },
}


def generate_tweets_via_llm(screen_name: str, profile: dict) -> list[dict]:
    """Use LLM to reconstruct key tweets/ideas from a well-known creator."""
    prompt = f"""你是一位熟悉 Twitter/X 知名创作者的内容研究员。

关于 @{screen_name} ({profile['name']}):
- 简介: {profile['bio']}
- 知名领域: {profile['known_for']}

请基于你对这位创作者的了解，还原他最有影响力的 30 条推文/观点。
这些应该是他真实表达过的核心思想，不是编造的。

要求：
- 每条推文保留英文原文
- 包含互动数据的合理估算
- 覆盖他的核心主题领域
- 按影响力排序

返回 JSON 数组格式：
[
  {{"text": "原始英文推文内容", "likes": 数字, "retweets": 数字, "topic": "主题分类"}},
  ...
]

只返回 JSON，不要其他内容。"""

    result = llm_chat_json(prompt, temperature=0.3)
    if isinstance(result, list):
        return result
    return []


def generate_digest_via_llm(screen_name: str, profile: dict) -> str:
    """Generate knowledge digest directly from LLM knowledge."""
    prompt = f"""你是一位擅长提炼思想精华的内容分析师。

请为 @{screen_name} ({profile['name']}) 生成一份完整的知识摘要。
他的核心领域: {profile['known_for']}

## 输出要求（Markdown 格式）：

### 1. 核心理念（3-5 个）
这位创作者最核心的思想观点，每个配上简要解释

### 2. 方法论与框架
他反复提到的具体方法、框架、工具

### 3. 金句集锦（15-20 条）
最有传播力的原始金句（保留英文原文），每条后附中文释义

### 4. 适用主题
这些思想可以延展到哪些内容方向（特别是：女性成长、职场发展、个人品牌、自我提升）

### 5. 内容风格
他的表达风格特点（句式、修辞、节奏）

请基于你对这位创作者的真实了解来写，确保准确性。"""

    return llm_chat(prompt, max_tokens=8000, temperature=0.5)


def build_knowledge_for_user(screen_name: str) -> dict:
    """Build complete knowledge base for a user."""
    profile = IP_PROFILES.get(screen_name)
    if not profile:
        raise ValueError(f"Unknown IP: {screen_name}. Available: {list(IP_PROFILES.keys())}")

    print(f"\n{'='*50}")
    print(f"Building knowledge base for @{screen_name}...")
    print(f"{'='*50}")

    # Step 1: Save profile
    print(f"  [1/3] Saving profile...")
    save_profile(screen_name, profile)

    # Step 2: Generate and save tweets
    print(f"  [2/3] Generating tweet reconstruction via LLM...")
    tweets = generate_tweets_via_llm(screen_name, profile)
    save_tweets(screen_name, tweets)
    print(f"        → {len(tweets)} tweets generated")

    # Step 3: Generate digest
    print(f"  [3/3] Generating knowledge digest via LLM...")
    digest = generate_digest_via_llm(screen_name, profile)
    save_digest(screen_name, digest)
    print(f"        → {len(digest)} chars digest")

    return {
        "name": screen_name,
        "profile": profile["name"],
        "tweets_count": len(tweets),
        "digest_length": len(digest),
    }


def main():
    parser = argparse.ArgumentParser(description="Build knowledge base offline (no browser)")
    parser.add_argument("--users", nargs="+", default=["dan_koe", "naval"],
                        help="IP handles to build KB for")
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
            print("No knowledge bases found.")
            return
        for kb in kbs:
            print(f"  {kb['name']}: {kb['tweet_count']} tweets, digest: {'✓' if kb['has_digest'] else '✗'}")
        return

    results = []
    for user in args.users:
        try:
            result = build_knowledge_for_user(user)
            results.append(result)
            print(f"\n✓ @{user} done: {result['tweets_count']} tweets, {result['digest_length']} chars digest")
        except Exception as e:
            print(f"\n✗ @{user} failed: {e}")
            logging.exception(f"Failed to build KB for @{user}")

    print(f"\n{'='*50}")
    print("Knowledge bases:")
    for kb in list_knowledge_bases():
        print(f"  {kb['name']}: {kb['tweet_count']} tweets, digest: {'✓' if kb['has_digest'] else '✗'}")


if __name__ == "__main__":
    main()
