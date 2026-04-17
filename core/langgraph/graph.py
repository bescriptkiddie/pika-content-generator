"""PikaEngine StateGraph Assembly"""

from langgraph.graph import StateGraph, END

from .state import PipelineState
from .nodes.acquire import acquire_node
from .nodes.analyze import analyze_node
from .nodes.generate import generate_node
from .nodes.risk_gate import risk_gate_node
from .nodes.execute import execute_node
from .nodes.feedback import feedback_node


def should_risk_gate(state: PipelineState) -> str:
    if state["scene"] in ("quant_a_stock", "quant_crypto"):
        return "risk_gate"
    return "execute"


def after_risk_gate(state: PipelineState) -> str:
    if not state.get("risk_check_passed", True):
        return "human_review"
    return "execute"


def human_review_node(state: PipelineState) -> dict:
    """Placeholder — LangGraph interrupt_before pauses here for human input."""
    return {"requires_human_review": False}


def build_graph(checkpointer=None):
    builder = StateGraph(PipelineState)

    builder.add_node("acquire", acquire_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("generate", generate_node)
    builder.add_node("risk_gate", risk_gate_node)
    builder.add_node("execute", execute_node)
    builder.add_node("feedback", feedback_node)
    builder.add_node("human_review", human_review_node)

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
