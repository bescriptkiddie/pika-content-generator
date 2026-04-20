from __future__ import annotations

from typing import Any

STAGE_ORDER = [
    "acquire",
    "analyze",
    "generate",
    "risk_gate",
    "execute",
    "feedback",
]


STAGE_KEY_MAP = {
    "acquire": "m1_acquire",
    "analyze": "m2_analyze",
    "generate": "m3_generate",
    "risk_gate": "m3_5_risk_gate",
    "execute": "m4_execute",
    "feedback": "m5_feedback",
}


def load_policy(scene_name: str, base_scene: str, pipeline: dict[str, Any]) -> dict[str, Any]:
    execute_cfg = pipeline.get("m4_execute", {}).get("config", {})
    risk_cfg = pipeline.get("m3_5_risk_gate", {})
    enabled_stages = [stage for stage in STAGE_ORDER if _stage_enabled(stage, base_scene, pipeline)]
    return {
        "scene_name": scene_name,
        "base_scene": base_scene,
        "enabled_stages": enabled_stages,
        "requires_human_review": bool(
            execute_cfg.get("require_confirmation")
            or execute_cfg.get("need_review")
            or execute_cfg.get("auto_publish") is False
            or risk_cfg.get("enabled")
        ),
        "auto_publish": bool(execute_cfg.get("auto_publish", False)),
        "checkpoint": True,
        "max_retries": 2,
        "artifact_policy": "stage_outputs",
    }


def _stage_enabled(stage: str, base_scene: str, pipeline: dict[str, Any]) -> bool:
    if stage == "risk_gate":
        risk_cfg = pipeline.get("m3_5_risk_gate", {})
        return base_scene in {"quant_a_stock", "quant_crypto"} or bool(risk_cfg.get("enabled"))
    stage_key = STAGE_KEY_MAP[stage]
    return stage_key in pipeline or stage in {"acquire", "analyze", "generate", "execute", "feedback"}
