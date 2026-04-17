"""PikaEngine Pipeline State Definition"""

from typing import TypedDict, Literal, Optional


class PipelineState(TypedDict, total=False):
    # 场景标识
    scene: Literal[
        "xiaohongshu", "gallup", "geo",
        "quant_a_stock", "quant_crypto"
    ]

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
