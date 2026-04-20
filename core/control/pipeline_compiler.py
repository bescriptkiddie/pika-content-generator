from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .policy_loader import STAGE_KEY_MAP, load_policy
from .scene_registry import resolve_scene


def load_scene_configs(config_path: str) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return config.get("scenes", {})


def compile_run_plan(scene: str, config_path: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    scene_configs = load_scene_configs(config_path)
    resolved_scene, base_scene, scene_config = resolve_scene(scene, scene_configs)
    pipeline = scene_config.get("pipeline", {})
    policy = load_policy(resolved_scene, base_scene, pipeline)
    stage_configs = _build_stage_configs(base_scene, pipeline)
    run_plan = {
        "scene": resolved_scene,
        "base_scene": base_scene,
        "name": scene_config.get("name", resolved_scene),
        "config_path": str(Path(config_path).resolve()),
        "stages": policy["enabled_stages"],
        "stage_configs": stage_configs,
        "bindings": {
            stage: stage_configs.get(stage, {}).get("binding", f"{base_scene}.{stage}")
            for stage in policy["enabled_stages"]
        },
        "policy": policy,
        "overrides": overrides or {},
    }
    if overrides:
        _apply_overrides(run_plan, overrides)
    return run_plan


def _build_stage_configs(base_scene: str, pipeline: dict[str, Any]) -> dict[str, Any]:
    stage_configs: dict[str, Any] = {}
    for stage, pipeline_key in STAGE_KEY_MAP.items():
        pipeline_entry = pipeline.get(pipeline_key, {})
        stage_configs[stage] = {
            "binding": f"{base_scene}.{stage}",
            "config": pipeline_entry.get("config", {}),
            "type": pipeline_entry.get("type", pipeline_entry.get("template", "")),
            "model": pipeline_entry.get("model", ""),
            "knowledge_sources": pipeline_entry.get("knowledge_sources", []),
        }
    return stage_configs


def _apply_overrides(run_plan: dict[str, Any], overrides: dict[str, Any]) -> None:
    stage_overrides = overrides.get("stage_configs", {})
    for stage, values in stage_overrides.items():
        run_plan["stage_configs"].setdefault(stage, {}).update(values)
    if "policy" in overrides:
        run_plan["policy"].update(overrides["policy"])
