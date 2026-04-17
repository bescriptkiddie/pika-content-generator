"""M4: Execution Node"""

from ..state import PipelineState


def execute_node(state: PipelineState) -> dict:
    scene = state["scene"]
    content = state.get("generated_content", [])

    if not content:
        return {"execution_results": []}

    handlers = {
        "xiaohongshu": _execute_xiaohongshu,
        "gallup": _execute_gallup,
        "geo": _execute_geo,
        "quant_a_stock": _execute_trade,
        "quant_crypto": _execute_trade,
    }

    handler = handlers.get(scene, _execute_noop)
    return {"execution_results": handler(content, state)}


def _execute_xiaohongshu(content: list[dict], state: PipelineState) -> list[dict]:
    # TODO: web-access CDP 发布到小红书创作者中心
    results = []
    for item in content:
        results.append({
            "status": "draft_created",
            "title": item.get("title", ""),
            "platform": "xiaohongshu",
        })
    return results


def _execute_gallup(content: list[dict], state: PipelineState) -> list[dict]:
    # TODO: 交付给教练（API/邮件/消息）
    return [{"status": "delivered", "platform": "gallup"}]


def _execute_geo(content: list[dict], state: PipelineState) -> list[dict]:
    # TODO: 调用 GEOFlow API 入库
    return [{"status": "queued", "platform": "geoflow"}]


def _execute_trade(content: list[dict], state: PipelineState) -> list[dict]:
    # TODO: 调用 CCXT / 券商 API 下单
    # 默认 require_confirmation: true，仅记录信号
    results = []
    for signal in content:
        results.append({
            "status": "signal_logged",
            "signal": signal,
            "executed": False,
        })
    return results


def _execute_noop(content: list[dict], state: PipelineState) -> list[dict]:
    return [{"status": "noop"}]
