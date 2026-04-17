"""PikaEngine FastAPI server — triggered by n8n or manual HTTP calls"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json

from core.langgraph.graph import build_graph

app = FastAPI(title="PikaEngine API", version="0.1.0")
graph = build_graph()


class RunRequest(BaseModel):
    scene: str
    acquire_config: dict = {}
    thread_id: str | None = None


@app.post("/run")
async def run_pipeline(req: RunRequest):
    if req.scene not in ("xiaohongshu", "gallup", "geo", "quant_a_stock", "quant_crypto"):
        raise HTTPException(400, f"Unknown scene: {req.scene}")

    initial_state = {
        "scene": req.scene,
        "acquire_config": req.acquire_config,
        "raw_data": [],
        "analyzed_items": [],
        "top_items": [],
        "generated_content": [],
        "risk_check_passed": True,
        "risk_adjustments": [],
        "execution_results": [],
        "feedback_data": {},
        "error": None,
        "retry_count": 0,
        "requires_human_review": False,
    }

    config = {}
    if req.thread_id:
        config["configurable"] = {"thread_id": req.thread_id}

    result = graph.invoke(initial_state, config=config if config else None)

    return {
        "scene": req.scene,
        "feedback": result.get("feedback_data", {}),
        "execution_results": result.get("execution_results", []),
        "risk_adjustments": result.get("risk_adjustments", []),
        "error": result.get("error"),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "PikaEngine"}
