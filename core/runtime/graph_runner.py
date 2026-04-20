from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from core.control.pipeline_compiler import compile_run_plan
from core.langgraph.graph import build_graph

from .artifact_store import ArtifactStore
from .checkpointer_factory import build_checkpointer
from .event_logger import EventLogger
from .run_store import RunStore


class GraphRunner:
    def __init__(self, config_path: str, storage_path: str | None = None):
        self.config_path = config_path
        self.run_store = RunStore()
        self.artifact_store = ArtifactStore(self.run_store)
        self.event_logger = EventLogger(self.run_store)
        self.checkpointer = build_checkpointer(storage_path)
        self.graph = build_graph(
            checkpointer=self.checkpointer,
            event_logger=self.event_logger,
            artifact_store=self.artifact_store,
        )

    def run(
        self,
        *,
        scene: str,
        trigger: str = "manual",
        stage_config_overrides: dict[str, Any] | None = None,
        run_id: str | None = None,
        thread_id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        run_id = run_id or self._new_run_id(scene)
        run_plan = compile_run_plan(
            scene=scene,
            config_path=self.config_path,
            overrides={"stage_configs": stage_config_overrides or {}},
        )
        if dry_run:
            run_plan["policy"]["auto_publish"] = False
            run_plan["policy"]["dry_run"] = True
            run_plan["stage_configs"].setdefault("execute", {}).setdefault("config", {})["auto_publish"] = False
        initial_state = self._build_initial_state(run_plan)
        initial_state["run_id"] = run_id
        initial_state["trigger"] = trigger
        self.run_store.init_run(
            run_id,
            {
                "scene": run_plan["scene"],
                "base_scene": run_plan["base_scene"],
                "trigger": trigger,
                "thread_id": thread_id or run_id,
                "status": "running",
                "run_plan": run_plan,
                "started_at": datetime.now().isoformat(),
            },
        )
        self.event_logger.log(run_id, {"type": "run_started", "scene": run_plan["scene"]})
        invoke_config = {"configurable": {"thread_id": thread_id or run_id}}
        try:
            result = self.graph.invoke(initial_state, config=invoke_config)
            final_status = self._final_status(result)
            self.run_store.update_run(
                run_id,
                {
                    "status": final_status,
                    "finished_at": datetime.now().isoformat(),
                    "feedback": result.get("feedback_data", {}),
                    "error": result.get("error"),
                    "failure_state": result.get("failure_state"),
                    "action_required": result.get("action_required", "none"),
                    "degraded": result.get("degraded", False),
                },
            )
            self.event_logger.log(
                run_id,
                {
                    "type": "run_finished",
                    "status": final_status,
                    "error": result.get("error"),
                    "failure_state": result.get("failure_state"),
                    "action_required": result.get("action_required", "none"),
                },
            )
            return {"run_id": run_id, "run_plan": run_plan, "result": result}
        except Exception as exc:
            self.run_store.update_run(
                run_id,
                {
                    "status": "failed",
                    "finished_at": datetime.now().isoformat(),
                    "error": str(exc),
                },
            )
            self.event_logger.log(run_id, {"type": "run_failed", "error": str(exc)})
            raise

    @staticmethod
    def _build_initial_state(run_plan: dict[str, Any]) -> dict[str, Any]:
        acquire_cfg = dict(run_plan["stage_configs"].get("acquire", {}).get("config", {}))
        execute_cfg = dict(run_plan["stage_configs"].get("execute", {}).get("config", {}))
        if execute_cfg:
            acquire_cfg.update({k: v for k, v in execute_cfg.items() if k not in acquire_cfg})
        return {
            "scene": run_plan["base_scene"],
            "scene_name": run_plan["scene"],
            "acquire_config": acquire_cfg,
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
            "requires_human_review": run_plan["policy"].get("requires_human_review", False),
            "run_plan": run_plan,
            "decision": {},
            "benchmark": {},
            "failure_state": None,
            "action_required": "none",
            "degraded": False,
        }

    @staticmethod
    def _final_status(result: dict[str, Any]) -> str:
        if result.get("action_required") and result.get("action_required") != "none":
            return "action_required"
        if result.get("error"):
            return "failed"
        if result.get("degraded"):
            return "degraded"
        return "completed"

    @staticmethod
    def _new_run_id(scene: str) -> str:
        slug = scene.replace("/", "-").replace("_", "-")
        return f"{slug}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
