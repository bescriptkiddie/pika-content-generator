"""M2: Analysis Node"""

import json
from ..state import PipelineState


def analyze_node(state: PipelineState) -> dict:
    scene = state["scene"]
    raw_data = state.get("raw_data", [])

    if not raw_data:
        return {"analyzed_items": [], "top_items": []}

    handlers = {
        "xiaohongshu": _analyze_trending,
        "gallup": _analyze_passthrough,
        "geo": _analyze_passthrough,
        "quant_a_stock": _analyze_signal,
        "quant_crypto": _analyze_signal,
    }

    handler = handlers.get(scene, _analyze_passthrough)
    return handler(raw_data, state.get("acquire_config", {}))


def _analyze_trending(raw_data: list[dict], config: dict) -> dict:
    # TODO: LLM 热点匹配度打分
    # 暂时按原始顺序取 top N
    top_n = config.get("top_n", 5)
    return {
        "analyzed_items": raw_data,
        "top_items": raw_data[:top_n],
    }


def _analyze_signal(raw_data: list[dict], config: dict) -> dict:
    # TODO: 接入朋友的策略模块计算信号
    return {
        "analyzed_items": raw_data,
        "top_items": raw_data,
    }


def _analyze_passthrough(raw_data: list[dict], config: dict) -> dict:
    return {
        "analyzed_items": raw_data,
        "top_items": raw_data,
    }
