"""M3: Content Generation Node"""

from ..state import PipelineState


def generate_node(state: PipelineState) -> dict:
    scene = state["scene"]
    top_items = state.get("top_items", [])

    if not top_items:
        return {"generated_content": []}

    handlers = {
        "xiaohongshu": _generate_xiaohongshu,
        "gallup": _generate_report,
        "geo": _generate_article,
        "quant_a_stock": _generate_signal,
        "quant_crypto": _generate_signal,
    }

    handler = handlers.get(scene, _generate_passthrough)
    return {"generated_content": handler(top_items, state.get("acquire_config", {}))}


def _generate_xiaohongshu(items: list[dict], config: dict) -> list[dict]:
    # TODO: 调用 GEOFlow AI Engine 生成小红书图文
    generated = []
    for item in items:
        generated.append({
            "type": "xiaohongshu_post",
            "title": f"[AI生成] {item.get('title', '')}",
            "body": "",  # TODO: LLM 生成
            "tags": item.get("tags", []),
            "source_item": item,
        })
    return generated


def _generate_report(items: list[dict], config: dict) -> list[dict]:
    # TODO: 盖洛普教练报告生成
    return [{"type": "gallup_report", "items": items}]


def _generate_article(items: list[dict], config: dict) -> list[dict]:
    # TODO: GEO 文章生成（调用 GEOFlow）
    return [{"type": "geo_article", "items": items}]


def _generate_signal(items: list[dict], config: dict) -> list[dict]:
    # TODO: 交易信号格式化
    return [{"type": "trading_signal", "data": item} for item in items]


def _generate_passthrough(items: list[dict], config: dict) -> list[dict]:
    return items
