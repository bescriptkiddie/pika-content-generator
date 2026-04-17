"""PikaEngine CLI entry point"""

import argparse
import json
import yaml

from core.langgraph.graph import build_graph


def load_scene_config(config_path: str, scene: str) -> dict:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    scenes = config.get("scenes", {})
    if scene not in scenes:
        raise ValueError(f"Scene '{scene}' not found in config. Available: {list(scenes.keys())}")

    return scenes[scene]


def main():
    parser = argparse.ArgumentParser(description="PikaEngine — Multi-scene AI Content Engine")
    parser.add_argument("--scene", required=True, help="Scene to run (xiaohongshu/gallup/geo/quant_a_stock/quant_crypto)")
    parser.add_argument("--config", default="config/scenes.example.yaml", help="Scene config file")
    parser.add_argument("--thread-id", default=None, help="Thread ID for checkpoint resume")
    args = parser.parse_args()

    scene_config = load_scene_config(args.config, args.scene)
    pipeline = scene_config.get("pipeline", {})

    initial_state = {
        "scene": args.scene,
        "acquire_config": pipeline.get("m1_acquire", {}).get("config", {}),
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

    config = {}
    if args.thread_id:
        config["configurable"] = {"thread_id": args.thread_id}

    print(f"Running scene: {args.scene}")
    result = graph.invoke(initial_state, config=config if config else None)

    print("\n--- Result ---")
    print(json.dumps(result.get("feedback_data", {}), indent=2, ensure_ascii=False))
    print(f"Execution results: {len(result.get('execution_results', []))}")

    if result.get("risk_adjustments"):
        print(f"Risk adjustments: {json.dumps(result['risk_adjustments'], indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
