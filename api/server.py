"""PikaEngine FastAPI server — triggered by n8n or manual HTTP calls"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.runtime.graph_runner import GraphRunner

app = FastAPI(title="PikaEngine API", version="0.2.0")
runner = GraphRunner(config_path="config/scenes.example.yaml")


class RunRequest(BaseModel):
    scene: str
    trigger: str = "api"
    thread_id: str | None = None
    run_id: str | None = None
    dry_run: bool = False
    stage_config_overrides: dict = Field(default_factory=dict)


@app.post("/run")
async def run_pipeline(req: RunRequest):
    try:
        run = runner.run(
            scene=req.scene,
            trigger=req.trigger,
            run_id=req.run_id,
            thread_id=req.thread_id,
            dry_run=req.dry_run,
            stage_config_overrides=req.stage_config_overrides,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    result = run["result"]
    return {
        "run_id": run["run_id"],
        "scene": run["run_plan"]["scene"],
        "feedback": result.get("feedback_data", {}),
        "execution_results": result.get("execution_results", []),
        "risk_adjustments": result.get("risk_adjustments", []),
        "error": result.get("error"),
    }


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    payload = runner.run_store.read_run(run_id)
    if not payload:
        raise HTTPException(404, f"Run not found: {run_id}")
    return payload


@app.get("/runs/{run_id}/events")
async def get_run_events(run_id: str):
    events_path = runner.run_store.run_dir(run_id) / "events.jsonl"
    if not events_path.exists():
        raise HTTPException(404, f"Events not found: {run_id}")
    return {"run_id": run_id, "events": events_path.read_text(encoding="utf-8").splitlines()}


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "PikaEngine"}
