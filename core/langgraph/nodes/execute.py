"""M4: Execution Node"""

import json
import time
import logging
from ..state import PipelineState

log = logging.getLogger(__name__)


def execute_node(state: PipelineState) -> dict:
    scene = state["scene"]
    content = state.get("generated_content", [])

    if not content:
        log.warning(f"[M4] {scene}: no content to execute")
        return {"execution_results": []}

    handlers = {
        "xiaohongshu": _execute_xiaohongshu,
        "gallup": _execute_gallup,
        "geo": _execute_geo,
        "quant_a_stock": _execute_trade,
        "quant_crypto": _execute_trade,
    }

    handler = handlers.get(scene, _execute_noop)
    try:
        results = handler(content, state)
        log.info(f"[M4] {scene}: executed {len(results)} items")
        return {"execution_results": results}
    except Exception as e:
        log.error(f"[M4] {scene} execute failed: {e}")
        return {"execution_results": [{"status": "failed", "error": str(e)}]}


def _execute_xiaohongshu(content: list[dict], state: PipelineState) -> list[dict]:
    from ..tools.web_access import (
        cdp_available, cdp_open_tab, cdp_eval,
        cdp_click, cdp_close_tab, cdp_scroll,
    )

    config = state.get("acquire_config", {})
    auto_publish = config.get("auto_publish", False)
    results = []

    if not cdp_available():
        # CDP 不可用，保存到本地文件作为草稿
        return _save_drafts_locally(content)

    creator_url = "https://creator.xiaohongshu.com/publish/publish"

    for item in content:
        if item.get("type") != "xiaohongshu_post":
            continue

        title = item.get("title", "")
        body = item.get("body", "")
        tags = item.get("tags", [])
        hook = item.get("hook", "")

        # 组装完整正文
        full_body = body
        if hook:
            full_body += f"\n\n{hook}"
        if tags:
            full_body += "\n\n" + " ".join(tags)

        target_id = cdp_open_tab(creator_url, wait_seconds=3.0)
        if not target_id:
            results.append({"status": "failed", "title": title, "error": "无法打开创作者中心"})
            continue

        try:
            # 填写标题
            cdp_eval(target_id, f"""
                const titleInput = document.querySelector('#post-title, [placeholder*="标题"], input[class*="title"]');
                if (titleInput) {{
                    titleInput.focus();
                    titleInput.value = {json.dumps(title)};
                    titleInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                }}
            """)
            time.sleep(0.5)

            # 填写正文
            cdp_eval(target_id, f"""
                const editor = document.querySelector('.ql-editor, [contenteditable="true"], .ProseMirror');
                if (editor) {{
                    editor.focus();
                    editor.innerHTML = {json.dumps(full_body.replace(chr(10), '<br>'))};
                    editor.dispatchEvent(new Event('input', {{bubbles: true}}));
                }}
            """)
            time.sleep(0.5)

            if auto_publish:
                # 点击发布按钮
                cdp_click(target_id, 'button[class*="publish"], button[class*="submit"]')
                time.sleep(2.0)
                results.append({"status": "published", "title": title, "platform": "xiaohongshu"})
                log.info(f"[M4] published: {title[:40]}")
            else:
                # 仅创建草稿，不点发布
                results.append({"status": "draft_in_editor", "title": title, "platform": "xiaohongshu"})
                log.info(f"[M4] draft ready: {title[:40]}")

        except Exception as e:
            results.append({"status": "failed", "title": title, "error": str(e)})
            log.error(f"[M4] publish failed for '{title[:30]}': {e}")
        finally:
            if auto_publish:
                cdp_close_tab(target_id)
            # 不自动发布时保留标签页，让用户手动确认

    return results


def _save_drafts_locally(content: list[dict]) -> list[dict]:
    """CDP 不可用时，保存草稿到本地 JSON 文件"""
    import os
    from datetime import datetime

    drafts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "drafts")
    os.makedirs(drafts_dir, exist_ok=True)

    results = []
    for item in content:
        if item.get("type") != "xiaohongshu_post":
            continue

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"xhs_{timestamp}_{len(results)}.json"
        filepath = os.path.join(drafts_dir, filename)

        draft = {
            "title": item.get("title", ""),
            "body": item.get("body", ""),
            "tags": item.get("tags", []),
            "hook": item.get("hook", ""),
            "created_at": datetime.now().isoformat(),
            "status": "local_draft",
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False, indent=2)

        results.append({
            "status": "local_draft",
            "title": item.get("title", ""),
            "file": filepath,
        })
        log.info(f"[M4] saved local draft: {filepath}")

    return results


def _execute_gallup(content: list[dict], state: PipelineState) -> list[dict]:
    # TODO: 交付给教练（API/邮件/消息）
    return [{"status": "delivered", "platform": "gallup"}]


def _execute_geo(content: list[dict], state: PipelineState) -> list[dict]:
    from ..tools.geoflow_api import push_article_to_geoflow
    import os

    api_token = os.getenv("GEOFLOW_API_TOKEN", "")
    results = []

    for item in content:
        if item.get("type") != "geo_article":
            continue
        result = push_article_to_geoflow(
            title=item.get("title", ""),
            content=item.get("body", json.dumps(item.get("items", []))),
            api_token=api_token,
        )
        results.append({"status": "queued", "platform": "geoflow", "result": result})

    return results or [{"status": "noop", "platform": "geoflow"}]


def _execute_trade(content: list[dict], state: PipelineState) -> list[dict]:
    # 默认仅记录信号，不自动执行
    results = []
    for signal in content:
        results.append({
            "status": "signal_logged",
            "signal": signal,
            "executed": False,
        })
    return results


def _execute_noop(content: list[dict], state: PipelineState) -> list[dict]:
    return [{"status": "noop"}]
