import json
from pathlib import Path

from core.control.pipeline_compiler import compile_run_plan
from core.runtime.graph_runner import GraphRunner


def test_compile_run_plan_for_xiaohongshu_variant():
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    plan = compile_run_plan("xiaohongshu_trending", str(config_path))

    acquire_config = plan["stage_configs"]["acquire"]["config"]
    execute_config = plan["stage_configs"]["execute"]["config"]

    assert plan["scene"] == "xiaohongshu_trending"
    assert plan["base_scene"] == "xiaohongshu"
    assert "acquire" in plan["stages"]
    assert "generate" in plan["stages"]
    assert acquire_config["mode"] == "trending"
    assert acquire_config["browser_backend"] == "cdp_http"
    assert acquire_config["cdp_base"] == "http://127.0.0.1:3456"
    assert acquire_config["browser_request_timeout"] == 20
    assert acquire_config["provider_order"]["search"] == ["xhs_cli_search", "bb_search", "browser_search"]
    assert execute_config["browser_backend"] == "playwright_persistent"


def test_graph_runner_initial_state_merges_execute_browser_config():
    initial_state = GraphRunner._build_initial_state(
        {
            "base_scene": "xiaohongshu",
            "scene": "xiaohongshu",
            "policy": {"requires_human_review": False},
            "stage_configs": {
                "acquire": {"config": {"mode": "search", "keywords": ["AI工具"]}},
                "execute": {
                    "config": {
                        "browser_backend": "cdp_http",
                        "cdp_base": "http://127.0.0.1:3456",
                        "browser_request_timeout": 30,
                    }
                },
            },
        }
    )

    assert initial_state["acquire_config"]["mode"] == "search"
    assert initial_state["acquire_config"]["keywords"] == ["AI工具"]
    assert initial_state["acquire_config"]["browser_backend"] == "cdp_http"
    assert initial_state["acquire_config"]["cdp_base"] == "http://127.0.0.1:3456"
    assert initial_state["acquire_config"]["browser_request_timeout"] == 30



def test_xiaohongshu_runner_creates_run_artifacts(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    runner = GraphRunner(config_path=str(config_path))

    from core.langgraph.nodes import acquire as acquire_module
    from core.langgraph.nodes import analyze as analyze_module
    from core.langgraph.nodes import generate as generate_module
    from core.langgraph.nodes import execute as execute_module

    monkeypatch.setattr(acquire_module, "_acquire_xiaohongshu", lambda config: [
        {"title": "AI工具效率秘籍", "likes": 123, "author": "pika"}
    ])
    monkeypatch.setattr(analyze_module, "_analyze_xiaohongshu", lambda raw_data, config: {
        "analyzed_items": [{**raw_data[0], "score": 0.91, "reason": "高热度", "angle": "效率提效"}],
        "top_items": [{**raw_data[0], "score": 0.91, "reason": "高热度", "angle": "效率提效"}],
    })
    monkeypatch.setattr(generate_module, "_generate_xiaohongshu", lambda items, config: [
        {
            "type": "xiaohongshu_post",
            "title": "3个AI工具让我每天省2小时",
            "body": "正文",
            "tags": ["#AI工具"],
            "hook": "你最常用哪个？",
            "source_topic": items[0]["title"],
            "source_angle": items[0]["angle"],
        }
    ])
    monkeypatch.setattr(execute_module, "_execute_xiaohongshu", lambda content, state: [
        {
            "status": "local_draft",
            "title": content[0]["title"],
            "platform": "xiaohongshu",
            "fallback": True,
            "file": str(tmp_path / "draft.json"),
        }
    ])

    runner.run_store.root = tmp_path / "runs"
    runner.artifact_store.run_store = runner.run_store
    runner.event_logger.run_store = runner.run_store

    run = runner.run(scene="xiaohongshu_trending", trigger="test", dry_run=True, run_id="test-run")
    run_dir = runner.run_store.run_dir("test-run")

    assert run["result"]["feedback_data"]["scene_name"] == "xiaohongshu_trending"
    assert run["result"]["feedback_data"]["generated_count"] == 1
    assert run["result"]["feedback_data"]["draft_count"] == 1
    assert run["result"]["feedback_data"]["fallback_rate"] == 1.0
    assert run["result"]["feedback_data"]["action_required"] == "none"
    assert run["result"]["feedback_data"]["provider_success_count"] >= 0
    assert (run_dir / "run.json").exists()
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "artifacts" / "acquire.json").exists()
    assert (run_dir / "artifacts" / "feedback.json").exists()

    payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert payload["status"] in {"completed", "degraded"}



def test_xiaohongshu_runner_passes_browser_config_to_gateway(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    runner = GraphRunner(config_path=str(config_path))
    seen = {}

    from core.langgraph.nodes import analyze as analyze_module
    from core.langgraph.nodes import generate as generate_module
    from core.langgraph.nodes import execute as execute_module
    from core.langgraph.tools import signal_gateway as gateway_module

    def fake_acquire_signals(config):
        seen["config"] = dict(config)
        return {
            "items": [{"title": "AI工具趋势", "likes": 8, "author": "pika", "url": "https://www.xiaohongshu.com/explore/demo"}],
            "usable": True,
            "provider_trace": [
                {
                    "provider": "browser:search:AI工具",
                    "status": "success",
                    "usable": True,
                    "count": 1,
                    "usable_count": 1,
                    "retryable": False,
                    "action_required": "none",
                    "action_hint": "",
                    "reason": "",
                }
            ],
            "signal_summary": {"count": 1, "usable_count": 1, "usable": True},
            "failure_state": None,
            "action_required": "none",
            "degraded": False,
        }

    monkeypatch.setattr(gateway_module, "acquire_xiaohongshu_signals", fake_acquire_signals)
    monkeypatch.setattr(analyze_module, "_analyze_xiaohongshu", lambda raw_data, config: {
        "analyzed_items": [{**raw_data[0], "score": 0.88, "reason": "高热度", "angle": "工具清单"}],
        "top_items": [{**raw_data[0], "score": 0.88, "reason": "高热度", "angle": "工具清单"}],
    })
    monkeypatch.setattr(generate_module, "_generate_xiaohongshu", lambda items, config: [
        {
            "type": "xiaohongshu_post",
            "title": "AI工具趋势总结",
            "body": "正文",
            "tags": ["#AI工具"],
            "hook": "收藏备用",
            "source_topic": items[0]["title"],
            "source_angle": items[0]["angle"],
        }
    ])
    monkeypatch.setattr(execute_module, "_execute_xiaohongshu", lambda content, state: [
        {
            "status": "local_draft",
            "title": content[0]["title"],
            "platform": "xiaohongshu",
            "fallback": True,
            "file": str(tmp_path / "draft.json"),
        }
    ])

    runner.run_store.root = tmp_path / "runs"
    runner.artifact_store.run_store = runner.run_store
    runner.event_logger.run_store = runner.run_store

    runner.run(scene="xiaohongshu_trending", trigger="test", dry_run=True, run_id="config-pass-through")

    assert seen["config"]["browser_backend"] == "cdp_http"
    assert seen["config"]["cdp_base"] == "http://127.0.0.1:3456"
    assert seen["config"]["browser_request_timeout"] == 20
    assert seen["config"]["provider_order"]["feed"] == ["xhs_cli_feed", "bb_feed", "browser_feed"]



def test_xiaohongshu_provider_failure_state(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    runner = GraphRunner(config_path=str(config_path))

    from core.langgraph.nodes import analyze as analyze_module
    from core.langgraph.nodes import generate as generate_module
    from core.langgraph.nodes import execute as execute_module
    from core.langgraph.tools import signal_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "acquire_xiaohongshu_signals", lambda config: {
        "items": [],
        "usable": False,
        "provider_trace": [
            {
                "provider": "bb-browser:search:女性成长",
                "status": "unavailable",
                "usable": False,
                "count": 0,
                "usable_count": 0,
                "retryable": False,
                "action_required": "install_provider",
                "action_hint": "安装并配置 bb-browser",
                "reason": "bb-browser unavailable",
            }
        ],
        "signal_summary": {"count": 0, "usable_count": 0, "usable": False},
        "failure_state": {
            "kind": "unavailable",
            "stage": "acquire",
            "provider": "bb-browser:search:女性成长",
            "reason": "bb-browser unavailable",
            "retryable": False,
            "action_required": "install_provider",
            "action_hint": "安装并配置 bb-browser",
        },
        "action_required": "install_provider",
        "degraded": True,
    })
    monkeypatch.setattr(analyze_module, "_analyze_xiaohongshu", lambda raw_data, config: {
        "analyzed_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
        "top_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
    })
    monkeypatch.setattr(generate_module, "_generate_xiaohongshu", lambda items, config: [
        {
            "type": "xiaohongshu_post",
            "title": "seed title",
            "body": "正文",
            "tags": [],
            "hook": "",
            "source_topic": items[0]["title"],
            "source_angle": items[0]["angle"],
        }
    ])
    monkeypatch.setattr(execute_module, "_execute_xiaohongshu", lambda content, state: [
        {
            "status": "local_draft",
            "title": content[0]["title"],
            "platform": "xiaohongshu",
            "fallback": True,
            "file": str(tmp_path / "draft.json"),
        }
    ])

    runner.run_store.root = tmp_path / "runs"
    runner.artifact_store.run_store = runner.run_store
    runner.event_logger.run_store = runner.run_store

    run = runner.run(scene="xiaohongshu_trending", trigger="test", dry_run=True, run_id="provider-failure")
    feedback = run["result"]["feedback_data"]
    payload = json.loads((runner.run_store.run_dir("provider-failure") / "run.json").read_text(encoding="utf-8"))

    assert feedback["failure_state"]["kind"] == "unavailable"
    assert feedback["action_required"] == "install_provider"
    assert feedback["degraded"] is True
    assert payload["status"] == "action_required"
    assert feedback["provider_failure_count"] == 1



def test_xiaohongshu_browser_provider_failure_state(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    runner = GraphRunner(config_path=str(config_path))

    from core.langgraph.nodes import analyze as analyze_module
    from core.langgraph.nodes import generate as generate_module
    from core.langgraph.nodes import execute as execute_module
    from core.langgraph.tools import signal_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "acquire_xiaohongshu_signals", lambda config: {
        "items": [],
        "usable": False,
        "provider_trace": [
            {
                "provider": "browser:search:AI工具",
                "status": "auth_expired",
                "usable": False,
                "count": 0,
                "usable_count": 0,
                "retryable": False,
                "action_required": "reauth",
                "action_hint": "使用持久化浏览器 profile 手动登录小红书后重试",
                "reason": "browser profile has no xiaohongshu login session",
            }
        ],
        "signal_summary": {"count": 0, "usable_count": 0, "usable": False},
        "failure_state": {
            "kind": "auth_expired",
            "stage": "acquire",
            "provider": "browser:search:AI工具",
            "reason": "browser profile has no xiaohongshu login session",
            "retryable": False,
            "action_required": "reauth",
            "action_hint": "使用持久化浏览器 profile 手动登录小红书后重试",
        },
        "action_required": "reauth",
        "degraded": True,
    })
    monkeypatch.setattr(analyze_module, "_analyze_xiaohongshu", lambda raw_data, config: {
        "analyzed_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
        "top_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
    })
    monkeypatch.setattr(generate_module, "_generate_xiaohongshu", lambda items, config: [
        {
            "type": "xiaohongshu_post",
            "title": "seed title",
            "body": "正文",
            "tags": [],
            "hook": "",
            "source_topic": items[0]["title"],
            "source_angle": items[0]["angle"],
        }
    ])
    monkeypatch.setattr(execute_module, "_execute_xiaohongshu", lambda content, state: [
        {
            "status": "local_draft",
            "title": content[0]["title"],
            "platform": "xiaohongshu",
            "fallback": True,
            "file": str(tmp_path / "draft.json"),
        }
    ])

    runner.run_store.root = tmp_path / "runs"
    runner.artifact_store.run_store = runner.run_store
    runner.event_logger.run_store = runner.run_store

    run = runner.run(scene="xiaohongshu_trending", trigger="test", dry_run=True, run_id="browser-provider-failure")
    feedback = run["result"]["feedback_data"]
    payload = json.loads((runner.run_store.run_dir("browser-provider-failure") / "run.json").read_text(encoding="utf-8"))

    assert feedback["failure_state"]["kind"] == "auth_expired"
    assert feedback["failure_state"]["provider"] == "browser:search:AI工具"
    assert feedback["action_required"] == "reauth"
    assert feedback["degraded"] is True
    assert payload["status"] == "action_required"
    assert feedback["provider_trace"][0]["status"] == "auth_expired"



def test_xiaohongshu_provider_verification_required_state(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parents[2] / "config" / "scenes.example.yaml"
    runner = GraphRunner(config_path=str(config_path))

    from core.langgraph.nodes import analyze as analyze_module
    from core.langgraph.nodes import generate as generate_module
    from core.langgraph.nodes import execute as execute_module
    from core.langgraph.tools import signal_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "acquire_xiaohongshu_signals", lambda config: {
        "items": [],
        "usable": False,
        "provider_trace": [
            {
                "provider": "xhs-cli:feed",
                "status": "verification_required",
                "usable": False,
                "count": 1,
                "usable_count": 0,
                "retryable": False,
                "action_required": "verify",
                "action_hint": "按平台要求完成验证后重新执行 xhs login --qrcode",
                "reason": "xhs-cli QR login requires platform verification",
                "verification_required": True,
                "verify_type": "124",
                "verify_uuid": "824a93bd-7347-47e9-b54b-1a7b0a259ade",
            }
        ],
        "signal_summary": {"count": 0, "usable_count": 0, "usable": False},
        "failure_state": {
            "kind": "verification_required",
            "stage": "acquire",
            "provider": "xhs-cli:feed",
            "reason": "xhs-cli QR login requires platform verification",
            "retryable": False,
            "action_required": "verify",
            "action_hint": "按平台要求完成验证后重新执行 xhs login --qrcode",
            "verification_required": True,
            "verify_type": "124",
            "verify_uuid": "824a93bd-7347-47e9-b54b-1a7b0a259ade",
        },
        "action_required": "verify",
        "degraded": True,
    })
    monkeypatch.setattr(analyze_module, "_analyze_xiaohongshu", lambda raw_data, config: {
        "analyzed_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
        "top_items": [{**raw_data[0], "score": 0.7, "reason": "seed", "angle": "seed"}],
    })
    monkeypatch.setattr(generate_module, "_generate_xiaohongshu", lambda items, config: [
        {
            "type": "xiaohongshu_post",
            "title": "seed title",
            "body": "正文",
            "tags": [],
            "hook": "",
            "source_topic": items[0]["title"],
            "source_angle": items[0]["angle"],
        }
    ])
    monkeypatch.setattr(execute_module, "_execute_xiaohongshu", lambda content, state: [
        {
            "status": "local_draft",
            "title": content[0]["title"],
            "platform": "xiaohongshu",
            "fallback": True,
            "file": str(tmp_path / "draft.json"),
        }
    ])

    runner.run_store.root = tmp_path / "runs"
    runner.artifact_store.run_store = runner.run_store
    runner.event_logger.run_store = runner.run_store

    run = runner.run(scene="xiaohongshu_trending", trigger="test", dry_run=True, run_id="provider-verify")
    feedback = run["result"]["feedback_data"]
    payload = json.loads((runner.run_store.run_dir("provider-verify") / "run.json").read_text(encoding="utf-8"))

    assert feedback["failure_state"]["kind"] == "verification_required"
    assert feedback["failure_state"]["verify_type"] == "124"
    assert feedback["failure_state"]["verify_uuid"] == "824a93bd-7347-47e9-b54b-1a7b0a259ade"
    assert feedback["action_required"] == "verify"
    assert feedback["degraded"] is True
    assert payload["status"] == "action_required"
    assert feedback["provider_failure_count"] == 1
    assert feedback["provider_trace"][0]["status"] == "verification_required"
