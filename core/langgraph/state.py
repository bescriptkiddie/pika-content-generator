"""PikaEngine Pipeline State Definition"""

from typing import Any, Literal, Optional, TypedDict


class FailureState(TypedDict, total=False):
    kind: str
    stage: str
    provider: str
    reason: str
    retryable: bool
    action_required: str
    action_hint: str
    verification_required: bool
    verify_type: str
    verify_uuid: str


class PipelineState(TypedDict, total=False):
    # 场景标识
    scene: Literal[
        "xiaohongshu", "gallup", "geo",
        "quant_a_stock", "quant_crypto"
    ]
    scene_name: str
    run_id: str
    trigger: str

    # Control Plane
    run_plan: dict[str, Any]
    decision: dict[str, Any]
    benchmark: dict[str, Any]

    # 状态管理
    failure_state: FailureState
    action_required: str
    degraded: bool

    # M1 采集
    acquire_config: dict
    raw_data: list[dict]

    # M2 分析
    analyzed_items: list[dict]
    top_items: list[dict]

    # M3 生成
    generated_content: list[dict]

    # M3.5 风控（量化专用）
    risk_check_passed: bool
    risk_adjustments: list[dict]

    # M4 执行
    execution_results: list[dict]

    # M5 反馈
    feedback_data: dict

    # 流程控制
    error: Optional[str]
    retry_count: int
    requires_human_review: bool
