"""PikaEngine CLI entry point"""

import argparse
import json
import logging
import sys

import yaml

from core.langgraph.graph import build_graph


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def load_scene_config(config_path: str, scene: str) -> dict:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    scenes = config.get("scenes", {})
    if scene not in scenes:
        raise ValueError(f"Scene '{scene}' not found. Available: {list(scenes.keys())}")

    return scenes[scene]


def main():
    parser = argparse.ArgumentParser(description="PikaEngine — Multi-scene AI Content Engine")
    parser.add_argument("--scene", required=True,
                        help="Scene: xiaohongshu / gallup / geo / quant_a_stock / quant_crypto")
    parser.add_argument("--config", default="config/scenes.example.yaml",
                        help="Scene config YAML file")
    parser.add_argument("--thread-id", default=None,
                        help="Thread ID for checkpoint resume")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run acquire+analyze+generate only, skip execute")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("pika-engine")

    scene_config = load_scene_config(args.config, args.scene)
    pipeline = scene_config.get("pipeline", {})
    acquire_config = pipeline.get("m1_acquire", {}).get("config", {})

    if args.dry_run:
        acquire_config["auto_publish"] = False

    initial_state = {
        "scene": args.scene,
        "acquire_config": acquire_config,
        "raw_data": [],
        "analyzed_items": [],
        "top_items": [],
        "generated_content": [],
        "risk_check_passed": True,
        "risk_adjustments": [],
        "execution_results": [],
        "feedback_data": {},
        "error": None,
        "retry_count": 0,
        "requires_human_review": False,
    }

    graph = build_graph()

    invoke_config = {}
    if args.thread_id:
        invoke_config["configurable"] = {"thread_id": args.thread_id}

    log.info(f"Starting scene: {args.scene}")
    result = graph.invoke(initial_state, config=invoke_config if invoke_config else None)

    # Output
    print("\n" + "=" * 50)
    print(f"Scene: {args.scene}")
    print(f"Raw data: {len(result.get('raw_data', []))} items")
    print(f"Top items: {len(result.get('top_items', []))} items")
    print(f"Generated: {len(result.get('generated_content', []))} items")
    print(f"Executed: {len(result.get('execution_results', []))} items")

    feedback = result.get("feedback_data", {})
    if feedback:
        print(f"\nFeedback: {json.dumps(feedback, indent=2, ensure_ascii=False)}")

    if result.get("risk_adjustments"):
        print(f"\nRisk adjustments:")
        for adj in result["risk_adjustments"]:
            print(f"  - {adj.get('action')}: {adj.get('reason', '')}")

    if result.get("error"):
        print(f"\nError: {result['error']}")

    # Print generated content summaries
    for i, item in enumerate(result.get("generated_content", [])):
        title = item.get("title", "")
        print(f"\n--- Generated #{i+1}: {title[:60]} ---")
        body = item.get("body", "")
        if body:
            print(body[:200] + ("..." if len(body) > 200 else ""))

    print("=" * 50)


if __name__ == "__main__":
    main()
