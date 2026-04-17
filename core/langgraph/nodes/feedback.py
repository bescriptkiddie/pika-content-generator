"""M5: Feedback Node"""

from ..state import PipelineState


def feedback_node(state: PipelineState) -> dict:
    scene = state["scene"]
    results = state.get("execution_results", [])

    # TODO: 各场景的效果数据回收
    # - 小红书：阅读/互动/爆款率
    # - 盖洛普：教练满意度/续费
    # - GEO：排名/流量变化
    # - 量化：盈亏/夏普比率/最大回撤

    return {
        "feedback_data": {
            "scene": scene,
            "total_executed": len(results),
            "success_count": sum(
                1 for r in results
                if r.get("status") not in ("failed", "noop")
            ),
        }
    }
