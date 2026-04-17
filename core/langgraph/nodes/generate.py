"""M3: Content Generation Node"""

import json
import logging
from ..state import PipelineState

log = logging.getLogger(__name__)


def generate_node(state: PipelineState) -> dict:
    scene = state["scene"]
    top_items = state.get("top_items", [])

    if not top_items:
        log.warning(f"[M3] {scene}: no items to generate from")
        return {"generated_content": []}

    handlers = {
        "xiaohongshu": _generate_xiaohongshu,
        "gallup": _generate_report,
        "geo": _generate_article,
        "quant_a_stock": _generate_signal,
        "quant_crypto": _generate_signal,
    }

    handler = handlers.get(scene, _generate_passthrough)
    try:
        content = handler(top_items, state.get("acquire_config", {}))
        log.info(f"[M3] {scene}: generated {len(content)} items")
        return {"generated_content": content}
    except Exception as e:
        log.error(f"[M3] {scene} generate failed: {e}")
        return {"generated_content": [], "error": str(e)}


def _generate_xiaohongshu(items: list[dict], config: dict) -> list[dict]:
    from ..tools.llm import llm_chat_json, llm_chat

    domain = config.get("domain", "通用")
    brand_voice = config.get("brand_voice", "真诚分享、有干货、接地气")
    generated = []

    for item in items:
        title = item.get("title", "")
        angle = item.get("angle", "")
        detail_content = item.get("detail", {}).get("content", "")

        prompt = f"""你是小红书爆款内容创作者。根据以下热点话题，创作一篇小红书笔记。

话题：{title}
切入角度：{angle}
领域：{domain}
风格要求：{brand_voice}
{"参考内容：" + detail_content[:500] if detail_content else ""}

创作要求：
1. 标题：吸引眼球，包含emoji，15-25字，制造好奇心或价值感
2. 正文：300-800字，分段清晰，开头抓人，每段有要点
3. 标签：5-8个相关话题标签，以#开头
4. 互动引导：结尾加一句引导评论的话

返回JSON格式：
{{
  "title": "笔记标题",
  "body": "正文内容（用\\n分段）",
  "tags": ["#标签1", "#标签2"],
  "hook": "互动引导语"
}}"""

        result = llm_chat_json(prompt)

        if result and isinstance(result, dict):
            generated.append({
                "type": "xiaohongshu_post",
                "title": result.get("title", title),
                "body": result.get("body", ""),
                "tags": result.get("tags", []),
                "hook": result.get("hook", ""),
                "source_topic": title,
                "source_angle": angle,
            })
            log.info(f"[M3] generated post: {result.get('title', '')[:40]}")
        else:
            # LLM JSON 解析失败，尝试纯文本生成
            text_prompt = f"""为小红书话题「{title}」创作一篇笔记。
角度：{angle}，领域：{domain}，风格：{brand_voice}。
包含标题、正文（300-800字）和5-8个标签。"""

            raw_text = llm_chat(text_prompt)
            generated.append({
                "type": "xiaohongshu_post",
                "title": title,
                "body": raw_text,
                "tags": [],
                "hook": "",
                "source_topic": title,
                "source_angle": angle,
                "raw_generation": True,
            })

    return generated


def _generate_report(items: list[dict], config: dict) -> list[dict]:
    # TODO: 盖洛普教练报告生成
    return [{"type": "gallup_report", "items": items}]


def _generate_article(items: list[dict], config: dict) -> list[dict]:
    # TODO: GEO 文章生成（调用 GEOFlow API）
    return [{"type": "geo_article", "items": items}]


def _generate_signal(items: list[dict], config: dict) -> list[dict]:
    return [{"type": "trading_signal", "data": item} for item in items]


def _generate_passthrough(items: list[dict], config: dict) -> list[dict]:
    return items
