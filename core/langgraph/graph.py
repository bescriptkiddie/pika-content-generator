"""PikaEngine StateGraph Assembly"""

from __future__ import annotations

import time
from typing import Callable

from langgraph.graph import END, StateGraph

from .nodes.acquire import acquire_node
from .nodes.analyze import analyze_node
from .nodes.execute import execute_node
from .nodes.feedback import feedback_node
from .nodes.generate import generate_node
from .nodes.risk_gate import risk_gate_node
from .state import PipelineState


def should_risk_gate(state: PipelineState) -> str:
    run_plan = state.get("run_plan", {})
    enabled_stages = set(run_plan.get("stages", []))
    if "risk_gate" in enabled_stages and state["scene"] in ("quant_a_stock", "quant_crypto"):
        return "risk_gate"
    return "execute"


def after_risk_gate(state: PipelineState) -> str:
    if not state.get("risk_check_passed", True):
        return "human_review"
    return "execute"


def human_review_node(state: PipelineState) -> dict:
    """Placeholder — LangGraph interrupt_before pauses here for human input."""
    return {"requires_human_review": False}


def build_graph(checkpointer=None, event_logger=None, artifact_store=None):
    builder = StateGraph(PipelineState)

    builder.add_node("acquire", _wrap_node("acquire", acquire_node, event_logger, artifact_store))
    builder.add_node("analyze", _wrap_node("analyze", analyze_node, event_logger, artifact_store))
    builder.add_node("generate", _wrap_node("generate", generate_node, event_logger, artifact_store))
    builder.add_node("risk_gate", _wrap_node("risk_gate", risk_gate_node, event_logger, artifact_store))
    builder.add_node("execute", _wrap_node("execute", execute_node, event_logger, artifact_store))
    builder.add_node("feedback", _wrap_node("feedback", feedback_node, event_logger, artifact_store))
    builder.add_node("human_review", _wrap_node("human_review", human_review_node, event_logger, artifact_store))

    builder.set_entry_point("acquire")
    builder.add_edge("acquire", "analyze")
    builder.add_edge("analyze", "generate")

    builder.add_conditional_edges("generate", should_risk_gate, {
        "risk_gate": "risk_gate",
        "execute": "execute",
    })

    builder.add_conditional_edges("risk_gate", after_risk_gate, {
        "human_review": "human_review",
        "execute": "execute",
    })

    builder.add_edge("human_review", "execute")
    builder.add_edge("execute", "feedback")
    builder.add_edge("feedback", END)

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
        compile_kwargs["interrupt_before"] = ["human_review"]

    return builder.compile(**compile_kwargs)


def _wrap_node(stage: str, node: Callable[[PipelineState], dict], event_logger=None, artifact_store=None):
    def wrapped(state: PipelineState) -> dict:
        run_id = state.get("run_id", "")
        started_at = time.perf_counter()
        if event_logger and run_id:
            event_logger.log(run_id, {"type": "stage_started", "stage": stage})
        try:
            result = node(state)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if artifact_store and run_id:
                artifact_store.write_stage_artifact(run_id, stage, result)
            if event_logger and run_id:
                event_logger.log(
                    run_id,
                    {
                        "type": "stage_finished",
                        "stage": stage,
                        "status": "success",
                        "duration_ms": duration_ms,
                    },
                )
            return result
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if event_logger and run_id:
                event_logger.log(
                    run_id,
                    {
                        "type": "stage_finished",
                        "stage": stage,
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                )
            raise

    return wrapped
