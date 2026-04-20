"""M5: Feedback Node"""

from ..state import PipelineState


BENCHMARK_THRESHOLDS = {
    "min_raw_items": 1,
    "min_top_items": 1,
    "min_generated_items": 1,
    "max_error_count": 0,
}



def feedback_node(state: PipelineState) -> dict:
    scene = state["scene"]
    results = state.get("execution_results", [])
    raw_items = state.get("raw_data", [])
    top_items = state.get("top_items", [])
    generated = state.get("generated_content", [])
    decision = state.get("decision", {})
    failure_state = state.get("failure_state")
    action_required = state.get("action_required", "none")
    degraded = state.get("degraded", False)

    draft_count = sum(1 for item in results if item.get("status") in ("draft_in_editor", "local_draft"))
    published_count = sum(1 for item in results if item.get("status") == "published")
    fallback_count = sum(1 for item in results if item.get("fallback"))
    error_count = sum(1 for item in results if item.get("status") == "failed")
    success_count = sum(1 for item in results if item.get("status") not in ("failed", "noop"))

    provider_trace = decision.get("provider_trace", [])
    feedback_extensions = {
        "provider_success_count": sum(1 for trace in provider_trace if trace.get("status") == "success"),
        "provider_failure_count": sum(1 for trace in provider_trace if trace.get("status") in {"error", "timeout", "unavailable", "auth_expired", "verification_required"}),
        "provider_empty_count": sum(1 for trace in provider_trace if trace.get("status") == "empty"),
    }

    benchmark = {
        "raw_items": len(raw_items),
        "top_items": len(top_items),
        "generated_count": len(generated),
        "draft_count": draft_count,
        "published_count": published_count,
        "fallback_rate": (fallback_count / len(results)) if results else 0.0,
        "error_count": error_count,
        "run_status": "pass" if _passes_benchmark(len(raw_items), len(top_items), len(generated), error_count) else "fail",
        "provider_trace": provider_trace,
        "signal_summary": decision.get("signal_summary", {}),
        "fallback_seed_used": decision.get("fallback_seed_used", False),
        "failure_state": failure_state,
        "action_required": action_required,
        "degraded": degraded,
        **feedback_extensions,
    }

    feedback = {
        "scene": scene,
        "scene_name": state.get("scene_name", scene),
        "total_executed": len(results),
        "success_count": success_count,
        **benchmark,
    }

    return {
        "feedback_data": feedback,
        "benchmark": benchmark,
    }



def _passes_benchmark(raw_count: int, top_count: int, generated_count: int, error_count: int) -> bool:
    return (
        raw_count >= BENCHMARK_THRESHOLDS["min_raw_items"]
        and top_count >= BENCHMARK_THRESHOLDS["min_top_items"]
        and generated_count >= BENCHMARK_THRESHOLDS["min_generated_items"]
        and error_count <= BENCHMARK_THRESHOLDS["max_error_count"]
    )
