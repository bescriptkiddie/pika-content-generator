"""M2: Analysis Node"""

import json
import logging
from ..state import PipelineState

log = logging.getLogger(__name__)


def analyze_node(state: PipelineState) -> dict:
    scene = state["scene"]
    raw_data = state.get("raw_data", [])

    if not raw_data:
        log.warning(f"[M2] {scene}: no raw data to analyze")
        return {"analyzed_items": [], "top_items": []}

    handlers = {
        "xiaohongshu": _analyze_xiaohongshu,
        "gallup": _analyze_passthrough,
        "geo": _analyze_passthrough,
        "quant_a_stock": _analyze_signal,
        "quant_crypto": _analyze_signal,
    }

    handler = handlers.get(scene, _analyze_passthrough)
    try:
        result = handler(raw_data, state.get("acquire_config", {}))
        decision = state.get("decision", {})
        if scene == "xiaohongshu":
            decision = {
                **decision,
                "chosen_topics": [
                    {
                        "title": item.get("title", ""),
                        "score": item.get("score", 0),
                        "angle": item.get("angle", ""),
                        "reason": item.get("reason", ""),
                    }
                    for item in result.get("top_items", [])
                ],
            }
            result["decision"] = decision
        log.info(f"[M2] {scene}: analyzed {len(result.get('analyzed_items', []))} items, top {len(result.get('top_items', []))}")
        return result
    except Exception as e:
        log.error(f"[M2] {scene} analyze failed: {e}")
        return {"analyzed_items": raw_data, "top_items": raw_data[:5], "error": str(e)}


def _analyze_xiaohongshu(raw_data: list[dict], config: dict) -> dict:
    from ..tools.llm import llm_chat_json

    domain = config.get("domain", "通用")
    target_audience = config.get("target_audience", "年轻人")
    top_n = config.get("top_n", 5)

    items_for_analysis = []
    for i, item in enumerate(raw_data[:30]):
        entry = {
            "index": i,
            "title": item.get("title", "")[:80],
            "likes": item.get("likes", item.get("heat", "0")),
            "author": item.get("author", ""),
        }
        if item.get("source_platform"):
            entry["source_platform"] = item["source_platform"]
        if item.get("source_type") or item.get("source"):
            entry["source_type"] = item.get("source_type", item.get("source", ""))
        items_for_analysis.append(entry)

    prompt = f"""你是小红书内容运营专家。分析以下热门内容，结合「{domain}」领域，
为目标受众「{target_audience}」筛选最有爆款潜力的话题。

数据：
{json.dumps(items_for_analysis, ensure_ascii=False, indent=2)}

评估标准：
1. 话题热度和互动潜力
2. 与「{domain}」领域的关联度
3. 内容差异化空间
4. 目标受众匹配度
5. 跨平台话题的小红书适配潜力（来自微博/知乎/头条的话题是否能转化为小红书爆款）

返回JSON数组，每项包含：
- index: 原始数据索引
- score: 0-1 综合评分
- reason: 一句话评分理由
- angle: 建议的内容切入角度

按 score 降序排列，最多返回 {top_n} 项。"""

    scored = llm_chat_json(prompt)

    if not scored or not isinstance(scored, list):
        return {"analyzed_items": raw_data, "top_items": raw_data[:top_n]}

    analyzed = list(raw_data)
    for score_item in scored:
        idx = score_item.get("index", -1)
        if 0 <= idx < len(analyzed):
            analyzed[idx]["score"] = score_item.get("score", 0)
            analyzed[idx]["reason"] = score_item.get("reason", "")
            analyzed[idx]["angle"] = score_item.get("angle", "")

    top_items = []
    for score_item in scored[:top_n]:
        idx = score_item.get("index", -1)
        if 0 <= idx < len(raw_data):
            top_items.append({**raw_data[idx], **score_item})

    return {"analyzed_items": analyzed, "top_items": top_items}


def _analyze_signal(raw_data: list[dict], config: dict) -> dict:
    return {"analyzed_items": raw_data, "top_items": raw_data}


def _analyze_passthrough(raw_data: list[dict], config: dict) -> dict:
    return {"analyzed_items": raw_data, "top_items": raw_data}
