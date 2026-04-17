"""M3.5: Risk Gate Node (Quant only)"""

from ..state import PipelineState


MAX_POSITION_PCT = 0.20
MAX_DAILY_LOSS_PCT = 0.03
MAX_CRYPTO_POSITION_PCT = 0.15
MAX_CRYPTO_LOSS_PCT = 0.05


def risk_gate_node(state: PipelineState) -> dict:
    scene = state["scene"]
    signals = state.get("generated_content", [])
    adjustments = []

    max_pos = MAX_CRYPTO_POSITION_PCT if scene == "quant_crypto" else MAX_POSITION_PCT
    max_loss = MAX_CRYPTO_LOSS_PCT if scene == "quant_crypto" else MAX_DAILY_LOSS_PCT

    for signal in signals:
        data = signal.get("data", signal)

        # 仓位上限
        pos = data.get("position_pct", 0)
        if pos > max_pos:
            adjustments.append({
                "action": "downgrade",
                "field": "position_pct",
                "original": pos,
                "adjusted": max_pos,
                "reason": f"超过{max_pos*100:.0f}%仓位上限",
            })
            data["position_pct"] = max_pos

        # 日亏损上限
        loss = data.get("estimated_loss_pct", 0)
        if loss > max_loss:
            return {
                "risk_check_passed": False,
                "risk_adjustments": [{
                    "action": "reject",
                    "reason": f"预估亏损{loss*100:.1f}%超过{max_loss*100:.0f}%上限",
                }],
                "requires_human_review": True,
            }

    return {
        "risk_check_passed": True,
        "risk_adjustments": adjustments,
    }
