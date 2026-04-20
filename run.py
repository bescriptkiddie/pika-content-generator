"""PikaEngine CLI entry point"""

import argparse
import json
import logging
import sys

from core.runtime.graph_runner import GraphRunner


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(description="PikaEngine — Multi-scene AI Content Engine")
    parser.add_argument("--scene", required=True, help="Scene name from config/scenes.example.yaml")
    parser.add_argument("--config", default="config/scenes.example.yaml", help="Scene config YAML file")
    parser.add_argument("--thread-id", default=None, help="Thread ID for checkpoint resume")
    parser.add_argument("--run-id", default=None, help="Run ID for event/artifact storage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Run acquire+analyze+generate only, skip publish")
    args = parser.parse_args()

    setup_logging(args.verbose)
    runner = GraphRunner(config_path=args.config)
    run = runner.run(
        scene=args.scene,
        trigger="cli",
        run_id=args.run_id,
        thread_id=args.thread_id,
        dry_run=args.dry_run,
    )
    result = run["result"]

    print("\n" + "=" * 50)
    print(f"Run ID: {run['run_id']}")
    print(f"Scene: {run['run_plan']['scene']}")
    print(f"Raw data: {len(result.get('raw_data', []))} items")
    print(f"Top items: {len(result.get('top_items', []))} items")
    print(f"Generated: {len(result.get('generated_content', []))} items")
    print(f"Executed: {len(result.get('execution_results', []))} items")
    feedback = result.get("feedback_data", {})
    if feedback:
        print(f"\nFeedback: {json.dumps(feedback, indent=2, ensure_ascii=False)}")
    if result.get("error"):
        print(f"\nError: {result['error']}")
    for index, item in enumerate(result.get("generated_content", []), start=1):
        print(f"\n--- Generated #{index}: {item.get('title', '')[:60]} ---")
        body = item.get("body", "")
        if body:
            print(body[:200] + ("..." if len(body) > 200 else ""))
    print("=" * 50)


if __name__ == "__main__":
    main()
