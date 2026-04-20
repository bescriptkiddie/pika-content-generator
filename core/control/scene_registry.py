from __future__ import annotations

from typing import Any

BASE_SCENES = (
    "xiaohongshu",
    "gallup",
    "geo",
    "quant_a_stock",
    "quant_crypto",
)


def infer_base_scene(scene: str) -> str:
    if scene in BASE_SCENES:
        return scene
    for base_scene in BASE_SCENES:
        if scene.startswith(f"{base_scene}_"):
            return base_scene
    raise ValueError(f"Unsupported scene: {scene}")


def build_scene_aliases(scene_configs: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for scene_name in scene_configs:
        aliases[scene_name] = scene_name
        base_scene = infer_base_scene(scene_name)
        aliases.setdefault(base_scene, scene_name)
    return aliases


def resolve_scene(scene: str, scene_configs: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    aliases = build_scene_aliases(scene_configs)
    resolved_scene = aliases.get(scene)
    if not resolved_scene:
        raise ValueError(
            f"Scene '{scene}' not found. Available: {sorted(scene_configs.keys())}"
        )
    base_scene = infer_base_scene(resolved_scene)
    return resolved_scene, base_scene, scene_configs[resolved_scene]
